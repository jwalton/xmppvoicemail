XMPP Voicemail
==============

By Mick Thompson (dthompson@gmail.com) and Jason Walton (dev@lucid.thedreaming.org).

This project will allow you to receive voice mail and send and receive SMS
messages via an XMPP service, such as Google Chat.

Setup
-----

Dependencies: Google App Engine, Twilio account

 - Register for a free [Google App Engine](https://developers.google.com/appengine/)
   account.  Create a new app.  We'll assume you called your app XMPPVOICEMAIL;
   everywhere you see that in these instructions, replace it with the app you
   actually created.
 - Download and install a copy of the [Google App Engine SDK](https://developers.google.com/appengine/downloads)
 - Register for an account on [Twilio](https://www.twilio.com/).  Pick a phone
   number you like.  Note that this will work with a trial account, although
   you will only be able to send SMS messages to numbers you've verified, and
   incoming calls will get a recording telling them that you're using a trial
   account.  Set up the handler for calls to be:
   - Voice: http://XMPPVOICEMAIL.appspot.com/call
   - SMS: http://XMPPVOICEMAIL.appspot.com/sms
 - Copy app.yaml.dist to app.yaml.  Open up app.yaml and change the
   "application" from CHANGEME to XMPPVOICEMAIL.
 - Copy config.py.dist to config.py. Open up config.py, and fill in everything.
   Make especially sure you change your `ADMIN_PASSWORD`.
 - Launch the Google App Engine Launcher (it came with the App Engine SDK),
   and use it to deploy your app.
 - Point a web browser at http://XMPPVOICEMAIL.appspot.com/, and login with
   your password.

From here you can create new "contacts" by filling in a contact name and a
phone number.  When you create a contact, you'll receive an invite from them
in your XMPP client (i.e. Google Chat.)

Usage
-----

If you have a contact defined for "mom", then if mom sends you an SMS message,
you should get a chat message from mom@XMPPVOICEMAIL.appspotchat.com.  If you
send a reply back, it will automatically get forwarded to your mom, and it
will look like it came from your Twilio number.

If you're offline when mom sends you an SMS, her SMS will get sent to you by
email from mom@XMPPVOICEMAIL.appspotmail.com.  You can reply, and type your
reply in the message body (the subject for email replies will be ignored.)

If you get an SMS from someone you don't have listed as a contact, then you
will get an SMS from "xmppvoicemail@XMPPVOICEMAIL.appspotchat.com".  The
message will have the phone number in it.  You can reply (or send an SMS to
anyone) by replying with a message in the format "phonenumber: message"
(e.g. "613-555-1234: Hello", but without the quotes of course.)

Emails from unlisted contacts work slightly differently; the email will come
from an address like "16135551234@XMPPVOICEMAIL.appspotmail.com".  You can
send a reply just by replying to the email; again the subject will be ignored.

If someone calls your Twilio number, they'll be asked to leave a message.
The message will be transcribed and sent to you by XMPP or email, along with a
link to the original recording.  You can also reply to an voicemail a sms from
the chat.

