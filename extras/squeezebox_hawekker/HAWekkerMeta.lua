
--[[

=head1 NAME

applets.HAWekker.HAWekkerMeta - meta-informatie voor het HAWekker-applet

=cut
--]]


local oo            = require("loop.simple")

local AppletMeta    = require("jive.AppletMeta")

local appletManager = appletManager


module(...)
oo.class(_M, AppletMeta)


function jiveVersion(self)
	return 1, 1
end


function defaultSettings(self)
	return {
	}
end


function registerApplet(self)

end


function configureApplet(self)
	-- geen menu-ingang: dit applet draait op de achtergrond mee
	appletManager:loadApplet("HAWekker")
end
