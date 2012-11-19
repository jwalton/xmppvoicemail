import unittest

from google.appengine.api import app_identity
from google.appengine.ext import testbed
from google.appengine.api import xmpp


from xmppvoicemail import Owner, XmppVoiceMail, InvalidParametersException
from models import Contact
import phonenumberutils

class CommunicationsFixture:
    def __init__(self):
        self.mails = []
        self.xmppMessages = []
        self.xmppInvites = []
        self.sms = []
        self.ownerOnline = True
    
    def sendMail(self, sender, to, subject, body):
        self.mails.append({
            "sender": sender,
            "to": to,
            "subject": subject,
            "body": body
        })
    
    def sendXmppMessage(self, fromJid, toJid, message):
        self.xmppMessages.append({
            "fromJid": fromJid,
            "toJid": toJid,
            "message": message
        })
        return xmpp.NO_ERROR
        
    def sendXmppInvite(self, fromJid, toJid):
        self.xmppInvites.append({
            "fromJid": fromJid,
            "toJid": toJid
        })
        
    def getXmppPresence(self, jid):
        return self.ownerOnline

    def sendSMS(self, toNumber, body):
        self.sms.append({
            "toNumber": toNumber,
            "body": body
        })

class XmppVoiceMailTestCases(unittest.TestCase):
    def setUp(self):
        # Set up Google App Engine testbed
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_app_identity_stub()
        
        self.contactNumber = "+16135551234"
        
        # Set up some handy constants
        self._APP_ID = app_identity.get_application_id()
        self.MAIL_SUFFIX = '@' + self._APP_ID + '.appspotmail.com'
        self.XMPP_SUFFIX = '@' + self._APP_ID + '.appspotchat.com'
        
        self.ownerPhoneNumber = "+16135554444"
        self.ownerJid = "user@gmail.com"
        self.ownerEmailAddress = "user@test.com"
        self.owner = Owner(self.ownerPhoneNumber, self.ownerJid, self.ownerEmailAddress)
        self.xmppvoicemail = XmppVoiceMail(self.owner)
        self.communications = self.xmppvoicemail._communications = CommunicationsFixture()

        # Subscribe the default sender.
        defaultSender = Contact.getDefaultSender()
        defaultSender.subscribed = True
        defaultSender.put()
        
        
    def tearDown(self):
        self.testbed.deactivate()
        
    def createContact(self, subscribed):
        # Create a known contact
        Contact(
            name = "mrtest",
            phoneNumber = self.contactNumber,
            normalizedPhoneNumber=phonenumberutils.toNormalizedNumber(self.contactNumber),
            subscribed=subscribed).save()        
        
    def test_incomingSmsMessageFromUnknownUser(self):
        """
        Tests an incoming SMS message from an unknown user with xmppVoiceMail unsubscribed.
        """
        # Unsubscribe the default sender.
        defaultSender = Contact.getDefaultSender()
        defaultSender.subscribed = False
        defaultSender.put()

        # Send the SMS
        self.xmppvoicemail.handleIncomingSms("+16135551234", self.ownerPhoneNumber, "Hello")
        
        # Should get an email, since user is not subscribed to xmppVoiceMail via XMPP.
        self.assertEqual(1, len(self.communications.mails), "Should have sent an email.")
        message = self.communications.mails[0]
        self.assertEqual(
            '"xmppvoicemail" <16135551234' + self.MAIL_SUFFIX +'>',
            message['sender'])
        self.assertEqual(self.ownerEmailAddress, message['to'])
        self.assertEqual("Hello", message['subject'])
        
    def test_incomingSmsMessageFromUnknownUserSubscribed(self):
        """
        Tests an incoming SMS message from an unknown user with xmppVoiceMail subscribed.
        """
        # Send the SMS
        self.xmppvoicemail.handleIncomingSms("+16135551234", self.ownerPhoneNumber, "Hello")
        
        # Should get an XMPP from the default sender.
        self.assertEqual(1, len(self.communications.xmppMessages), "Should have sent an XMPP message")
        message = self.communications.xmppMessages[0]
        self.assertEqual(
            'xmppvoicemail' + self.XMPP_SUFFIX,
            message['fromJid'])
        self.assertEqual(self.ownerJid, message['toJid'])
        self.assertEqual("(613)555-1234: Hello", message['message'])

    def test_incomingSmsMessageFromKnownUserUnsubscribed(self):
        """
        Tests an incoming SMS message from a known user with user unsubscribed.
        """
        # Create a known contact
        self.createContact(subscribed=False)
            
        # Send the SMS
        self.xmppvoicemail.handleIncomingSms(self.contactNumber, self.ownerPhoneNumber, "Hello")
        
        # Should get an XMPP from the default sender.
        self.assertEqual(1, len(self.communications.xmppMessages), "Should have sent an XMPP message")
        message = self.communications.xmppMessages[0]
        self.assertEqual(
            'xmppvoicemail' + self.XMPP_SUFFIX,
            message['fromJid'])
        self.assertEqual(self.ownerJid, message['toJid'])
        self.assertEqual("(613)555-1234: Hello", message['message'])

    def test_incomingSmsMessageFromKnownUserSubscribed(self):
        """
        Tests an incoming SMS message from a known user with user subscribed.
        """
        # Create a known contact
        self.createContact(subscribed=True)
            
        # Send the SMS
        self.xmppvoicemail.handleIncomingSms(self.contactNumber, self.ownerPhoneNumber, "Hello")
        
        # Should get an XMPP from the contact.
        self.assertEqual(1, len(self.communications.xmppMessages), "Should have sent an XMPP message")
        message = self.communications.xmppMessages[0]
        self.assertEqual(
            'mrtest' + self.XMPP_SUFFIX,
            message['fromJid'])
        self.assertEqual(self.ownerJid, message['toJid'])
        self.assertEqual("Hello", message['message'])

    def test_incomingSmsMessageFromUnknownUserSubscribedOwnerOffline(self):
        """
        Tests an incoming SMS message from an unknown user with xmppVoiceMail subscribed.
        """
        # Set the owner as offline
        self.communications.ownerOnline = False

        # Create a known contact
        self.createContact(subscribed=True)
        
        # Send the SMS
        self.xmppvoicemail.handleIncomingSms(self.contactNumber, self.ownerPhoneNumber, "Hello")
        
        # Should get an email, since owner is offline.
        self.assertEqual(1, len(self.communications.mails), "Should have sent an email.")
        message = self.communications.mails[0]
        self.assertEqual(
            '"mrtest" <16135551234' + self.MAIL_SUFFIX +'>',
            message['sender'])
        self.assertEqual(self.ownerEmailAddress, message['to'])
        self.assertEqual("Hello", message['subject'])

    def test_incomingXmppForNumber(self):
        self.xmppvoicemail.handleIncomingXmpp(
            sender=self.ownerJid,
            to='xmppVoiceMail' + self.XMPP_SUFFIX,
            messageBody="(613)555-1234: Hello")
        
        # Should send an SMS to 555-1234
        self.assertEqual(1, len(self.communications.sms), "Should have sent an SMS")
        sms = self.communications.sms[0]
        self.assertEqual("+16135551234", sms["toNumber"])
        self.assertEqual("Hello", sms["body"])

    def test_incomingXmppForContact(self):
        self.createContact(subscribed=True)

        self.xmppvoicemail.handleIncomingXmpp(
            sender=self.ownerJid,
            to='mrtest' + self.XMPP_SUFFIX,
            messageBody="Hello")
        
        # Should send an SMS to 555-1234
        self.assertEqual(1, len(self.communications.sms), "Should have sent an SMS")
        sms = self.communications.sms[0]
        self.assertEqual("+16135551234", sms["toNumber"])
        self.assertEqual("Hello", sms["body"])

    def test_incomingXmppForInvalidNumber(self):
        with self.assertRaises(InvalidParametersException):
            self.xmppvoicemail.handleIncomingXmpp(
                sender=self.ownerJid,
                to='xmppVoiceMail' + self.XMPP_SUFFIX,
                messageBody="(613)555-123a: Hello")
        

# TODO: Incoming email tests

        
if __name__ == '__main__':
    unittest.main()