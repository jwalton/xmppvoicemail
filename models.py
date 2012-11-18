from google.appengine.ext import db

import phonenumberutils

def _getObjectByIdString(clazz, idString):
    if idString.isdigit():
        objectId = int(idString)
        return clazz.get_by_id(objectId)
    else:
        return clazz.get_by_key_name(idString)

class XmppUser(db.Model):
    """Tracks presence of user.
    """
    jid = db.StringProperty(required=True)
    presence = db.BooleanProperty(required=True)

    @staticmethod
    def getByJid(jid):
        q = db.GqlQuery("SELECT * FROM XmppUser WHERE jid = :1", jid)
        return q.get()

class Contact(db.Model):
    """Stores information about a contact.
    """
    name = db.StringProperty(required=True)
    """
    Storing phoneNumber and normalizedPhoneNumber violates the DRY principle,
    but there's no way to recover an E.164 number's formatting from the
    normalized number, and it's easier to search by normalized number, so
    here we are.
    """
    phoneNumber = db.StringProperty(required=True)
    normalizedPhoneNumber = db.StringProperty(required=True)
    subscribed = db.BooleanProperty(default=False, required=True)
    
    def toDict(self):
        return {
            "id": self.key().id_or_name(),
            "name": self.name,
            "phoneNumber": self.phoneNumber,
            "subscribed": self.subscribed,
            "isDefaultSender": self.isDefaultSender()
        }
        
    def isDefaultSender(self):
        return self.key().id_or_name() == "DEFAULT_SENDER"
    
    @staticmethod
    def getByIdString(idString):
        """
        Returns a contact given a string representing it's ID.  If contactIdStr
        can be parsed as number, this will look up the contact using the
        numeric ID.  Otherwise, this will look up the contact using the string
        as a key name.
        """
        return _getObjectByIdString(Contact, idString)
    
    @staticmethod
    def getByPhoneNumber(phoneNumber):
        normalizedNumber = phonenumberutils.toNormalizedNumber(phoneNumber)
        q = db.GqlQuery("SELECT * FROM Contact WHERE normalizedPhoneNumber = :1", normalizedNumber)
        return q.get()
    
    @staticmethod
    def getByName(name):
        q = db.GqlQuery("SELECT * FROM Contact WHERE name = :1", name.lower())
        return q.get()
    
    @staticmethod
    def getDefaultSender():
        # TODO: Think about using some caching here, since we get this guy
        # all the time.
        return Contact.get_or_insert("DEFAULT_SENDER",
            name="xmppVoiceMail",
            phoneNumber="*",
            normalizedPhoneNumber="*")
