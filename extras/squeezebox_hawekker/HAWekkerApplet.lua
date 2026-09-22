
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

In hetzelfde pakketje staat "now=<epoch>": de tijd van Home Assistant. Een
Squeezebox heeft geen ntp-client; hij zet zijn klok op het epoch dat hij via
zijn abonnement op /slim/datestatus binnenkrijgt. Music Assistant beantwoordt
dat abonnement niet - aioslimproto kent alleen playerstatus, serverstatus en
menustatus - dus loopt de klok ongemerkt weg. Wijkt hij meer dan een paar
seconden af, dan zetten we hem hier gelijk, langs hetzelfde pad als SqueezeOS
zelf: squeezeos_bsp.swclockSetEpoch() gevolgd door sys2hwclock().

=cut
--]]


local tonumber, tostring, pcall, require = tonumber, tostring, pcall, require

local os                 = require("os")
local math               = require("math")
local string             = require("string")
local oo                 = require("loop.simple")

local Applet             = require("jive.Applet")
local Framework          = require("jive.ui.Framework")
local Timer              = require("jive.ui.Timer")
local SocketUdp          = require("jive.net.SocketUdp")
local Player             = require("jive.slim.Player")

local jnt                = jnt
local iconbar            = iconbar
local appletManager      = appletManager


module(..., Framework.constants)
oo.class(_M, Applet)


-- poort waarop Home Assistant de wektijd aflevert
local LISTEN_PORT = 9997

-- alleen pakketjes van Home Assistant zelf zijn interessant
local HA_IP = "192.168.2.100"

-- hoe vaak we controleren of de speler nog weet dat er een wekker staat
local TICK = 60000

-- vanaf hoeveel seconden verschil we de klok gelijkzetten
local DRIFT = 5

-- zo kort voor de wektijd laten we de klok met rust
local WEKMARGE = 120


function init(self)
	-- laatste wektijd die Home Assistant doorgaf (epoch, 0 = geen wekker)
	self.wanted = 0
	-- wat we daarvan al aan de speler hebben doorgegeven
	self.applied = nil
	-- pas na het eerste bericht van Home Assistant weten we iets; daarvoor
	-- laten we de wektijd staan die AlarmSnooze zelf had bewaard
	self.gehoord = false
	-- tijd van Home Assistant uit het laatste pakketje (epoch, nil = geen)
	self.servertijd = nil

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

	-- de tijd in hetzelfde pakketje is optioneel: oudere versies van de
	-- integratie sturen alleen de wektijd
	self.servertijd = tonumber(string.match(chunk.data, "now%s*=%s*(%d+)"))

	-- niet vanuit de netwerktaak in de speler roeren, dat doet de timer zo
	local hand = Timer(10,
		function()
			-- eerst de klok, dan pas de wektimers die eraan hangen
			self:_klok()
			self:_apply()
		end,
		true	-- eenmalig
	)
	hand:start()
end


-- _klok
-- zet de klok van het toestel gelijk met die van Home Assistant. SqueezeOS
-- doet dit normaal met het epoch uit /slim/datestatus; Music Assistant stuurt
-- dat nooit, dus zonder dit loopt de klok weg.
function _klok(self)
	local server = self.servertijd
	self.servertijd = nil

	if not server then
		return
	end

	local verschil = server - os.time()
	if math.abs(verschil) < DRIFT then
		return
	end

	-- een wekker die zo afgaat niet onder de klok vandaan trekken: de
	-- RTC-timer van de MCU staat op de oude tijd gezet
	local wekker = self.applied or self.wanted
	if wekker and wekker > os.time() and wekker - os.time() <= WEKMARGE then
		log:info("klok loopt ", verschil, " s mis, maar de wekker gaat zo af - later")
		return
	end

	local goed, squeezeos = pcall(require, "squeezeos_bsp")
	if goed and squeezeos.swclockSetEpoch then
		-- hetzelfde pad als SqueezeboxBabyApplet:setDate()
		squeezeos.swclockSetEpoch(server)

		local gelukt, err = squeezeos.sys2hwclock()
		if not gelukt then
			log:warn("sys2hwclock() mislukte: ", tostring(err))
		end
	else
		-- oudere firmware zonder die aanroepen: dan maar via de shell
		log:warn("squeezeos_bsp kent swclockSetEpoch niet, val terug op date")
		os.execute("/bin/date -s " .. os.date("%Y.%m.%d-%H:%M:%S", server))
		os.execute("/sbin/hwclock -w -u")
	end

	log:info("klok ", verschil, " s bijgezet, staat nu op ", os.date("%c", server))

	if iconbar then
		iconbar:update()
	end
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
