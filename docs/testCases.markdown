Incoming XMPP
-------------

Run with --clear_datastore to clear out saved presence data. 

 - Login to admin console at http://localhost:8080/_ah/admin/xmpp
 - Click on XMPP tab
 - Set type to "Presence"
 - Fill in "From" with owner JID
 - Fill in "To" with "sms@&lt;appid&gt;.appspotchat.com"
 - Set status to Available
 - Click "Make Request"
 
In log, should see:
 
    User &lt;owner-JID&gt; became available.
    Creating DB entry for &lt;owner-JID&gt;
    
 - Change "Message Type" to "Chat Message"
 - In the "Chat", fill in "Hello"
 - Click "Make Request"
 
This should fail, since xmpp messages going to "sms@&lt;appid&gt;.appspotchat.com"
need to be in a special format.  In the log, you should see an XMPP message
sent to &lt;owner-JID&gt; with the message "ERROR: Use 'number:message' to send an SMS."
 
 - Change the "Chat" to "+16135551234: Hello"
 - Click "Make Request"
  
Log should show "SMS to +16135551234: Hello"

 - Change "To:" to a nickname
 - Change "Chat" back to "Hello"
 - Click "Make Request"

Incoming SMS:
-------------

Point a web browser at http://localhost:8080/sms?From=16132222222&To=16135555555&Body=Hello to simulate an incoming SMS message.
Replace 16135555555 with your configured Twilio number.

 - Make sure user's XMPP presence is as "Available".
 - Send request from 16132222222 with body "Hello"
 
Log should show an XMPP message to &lt;owner-JID&gt;, from sms, with the body: "(613)222-2222: Hello"
 
 - Send request from a nickname's phone number.

Log should show an XMPP message to &lt;owner-JID&gt;, from nickname, with the body: "Hello"

 - Change user's XMPP presence to "Unavailable"
 - Send the above SMS again

Log should show an email message to the owner's email address.

Incoming Email:
---------------

 - Login to admin console at http://localhost:8080/_ah/admin/xmpp
 - Click on the Inbound Mail tab
   - From: &lt;owner-email&gt;
   - To: 16135551234@&lt;appid&gt;.appspotmail.com
   - Subject: Blah
   - Message Body: Hello
   
Log should show "SMS to +16135551234: Hello"

 - Change the "To" to a nickname.
 - Change the message body to "Hello"

Log should show "SMS to &lt;contact's number&gt;: Hello"
 