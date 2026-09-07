
--[[

=head1 NAME

applets.HAWekker.HAWekkerApplet - wektijd van Home Assistant naar de eigen wekker-GUI

=head1 DESCRIPTION

Sinds de Squeezebox aan Music Assistant hangt is er geen server meer die een
wektijd doorgeeft: MA kent geen alarmen en zet alarm_state altijd op "none".
Dit applet neemt die rol over. Home Assistant stuurt de eerstvolgende wektijd
als UDP-pakketje naar poort 9997 - platte tekst "next=<epoch>", waarbij 0
betekent dat er geen wekker staat - en dit applet voert die tijd in hetzelfde
pad als vroeger de LMS: jnt:notify('playerAlarmState', ...).

Al het zichtbare werk doet SqueezeOS daarna zelf: AlarmSnoozeApplet zet het
belletje in de balk aan, start zijn RTCAlarmTimer en opent op de wektijd het
wekvenster met de klok die elke seconde meeloopt, terwijl Music Assistant de
radio speelt. Blijft het geluid uit, dan valt het toestel na een minuut terug
op zijn eigen wektoon.

Het belletje in de klok-screensaver hangt niet aan de iconbar maar aan
player:getAlarmState(), dus die zetten we er zelf bij.

=cut
--]]


local tonumber, tostring = tonumber, tostring

local os                 = require("os")
local string             = require("string")
local oo                 = require("loop.simple")

local Applet             = require("jive.Applet")
local Framework          = require("jive.ui.Framework")
local Timer              = require("jive.ui.Timer")
local SocketUdp          = require("jive.net.SocketUdp")
local Player             = require("jive.slim.Player")

local jnt                = jnt
local appletManager      = appletManager


module(..., Framework.constants)
oo.class(_M, Applet)


-- poort waarop Home Assistant de wektijd aflevert
local LISTEN_PORT = 9997

-- alleen pakketjes van Home Assistant zelf zijn interessant
local HA_IP = "192.168.2.100"

-- hoe vaak we controleren of de speler nog weet dat er een wekker staat
local TICK = 60000


function init(self)
	-- laatste wektijd die Home Assistant doorgaf (epoch, 0 = geen wekker)
	self.wanted = 0
	-- wat we daarvan al aan de speler hebben doorgegeven
	self.applied = nil
	-- pas na het eerste bericht van Home Assistant weten we iets; daarvoor
	-- laten we de wektijd staan die AlarmSnooze zelf had bewaard
	self.gehoord = false

	self.socket = SocketUdp(jnt,
		function(chunk, err)
			self:_sink(chunk, err)
		end,
		"HAWekker",
		LISTEN_PORT)

	-- eigen hartslag: herstelt het belletje als de speler opnieuw verbindt
	-- (een reconnect met Music Assistant wist alarmState weer)
	self.tick = Timer(TICK,
		function()
			self:_apply()
		end,
		false	-- herhalen
	)
	self.tick:start()

	log:info("luistert op udp poort ", LISTEN_PORT)

	return self
end


-- _sink
-- verwerkt een binnengekomen pakketje van Home Assistant
function _sink(self, chunk, err)
	if err then
		log:warn("udp fout: ", err)
		return
	end

	if not chunk or not chunk.data then
		return
	end

	if chunk.ip ~= HA_IP then
		log:warn("pakketje van onbekend adres genegeerd: ", tostring(chunk.ip))
		return
	end

	local epoch = tonumber(string.match(chunk.data, "next%s*=%s*(%d+)"))
	if not epoch then
		log:warn("onleesbaar pakketje: ", tostring(chunk.data))
		return
	end

	self.wanted = epoch
	self.gehoord = true

	-- niet vanuit de netwerktaak in de speler roeren, dat doet de timer zo
	local hand = Timer(10,
		function()
			self:_apply()
		end,
		true	-- eenmalig
	)
	hand:start()
end


-- _apply
-- geeft de gewenste wektijd door aan de speler, maar alleen als er iets
-- te veranderen valt
function _apply(self)
	if not self.gehoord then
		-- nog niets van Home Assistant gehoord
		return
	end

	local player = Player:getLocalPlayer()
	if not player then
		-- speler bestaat nog niet (vlak na het opstarten), volgende tik weer
		return
	end

	-- staat de wektijd al in het verleden, dan wachten we op de volgende
	-- opgave van Home Assistant; zelf wissen zou het lopende alarm storen
	if self.wanted > 0 and self.wanted <= os.time() then
		return
	end

	-- gaat de wekker die nu klaarstaat zo af, dan schuiven we een nieuwe,
	-- latere tijd even voor ons uit: hem nu doorgeven zou de wektimer vlak
	-- voor tijd afzetten. Een wekker die juist uit gaat (0) doen we wel
	-- meteen, anders blijft hij tegen de wens in afgaan.
	if self.applied and self.applied > os.time()
	   and self.applied - os.time() <= 90
	   and self.wanted > self.applied then
		return
	end

	local state = player:getAlarmState()

	if self.wanted == self.applied then
		if self.wanted > 0 and state == 'set' then
			return
		end
		if self.wanted == 0 and not state then
			return
		end
		log:info("alarmstatus was kwijt, opnieuw doorgeven")
	end

	self.applied = self.wanted

	if self.wanted > 0 then
		log:info("wekker staat op ", os.date("%c", self.wanted))
		-- voor het belletje in de klok-screensaver
		player:setAlarmState('set')
		-- hetzelfde bericht dat de LMS stuurde: AlarmSnooze zet hierop het
		-- belletje in de balk, de RTC-timer en de wektijd van de MCU
		jnt:notify('playerAlarmState', player, 'set', self.wanted)
	else
		log:info("geen wekker meer ingesteld")
		player:setAlarmState(nil)
		jnt:notify('playerAlarmState', player, 'none', nil)
	end

	self:_ververstScreensaver()
end


-- _ververstScreensaver
-- De klok-screensaver luistert alleen naar alarmberichten als de speler al
-- bestond toen hij openging. Vlak na het opstarten is dat niet zo, en dan blijft
-- het belletje op die klok weg tot het venster een keer opnieuw wordt opgebouwd.
-- Dat duwtje geven we eenmalig, bij de eerste wektijd na het opstarten.
function _ververstScreensaver(self)
	if self.ververst then
		return
	end
	self.ververst = true

	if not appletManager:callService("isScreensaverActive") then
		return
	end

	log:info("klok-screensaver opnieuw opbouwen voor het belletje")
	appletManager:callService("deactivateScreensaver")
	appletManager:callService("activateScreensaver")
end


function free(self)
	if self.tick then
		self.tick:stop()
	end
	return true
end


--[[

=head1 LICENSE

Zelfbouw voor Familie ten Haaf, in de stijl van de SqueezePlay-applets.

=cut
--]]
