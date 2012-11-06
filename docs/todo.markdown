 - Make it so nicknames are stored in the database.  You should be able to configure nicknames on the fly from a web page.
 - Automate test cases.
 - Add option for queuing XMPP messages if you are offline, instead of resorting to email.
 - Add option to forward calls to a land-line depending on where you are, with location detection from an Android app.
 - Figure out how to make XMPP resources use their phone number as the JID, and use a nickname.  This is supported by the XMPP protocol, but I don't see anything in the XMPP API provided by
 App Engine that would let us do this.  Might need to resort to building XMPP messages from
 raw XML (ugh).