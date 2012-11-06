import phonenumberutils
from google.appengine.ext import db

class XmppUser(db.Model):
    """Tracks presence of user.
    """
    jid = db.StringProperty(required=True)
    presence = db.BooleanProperty(required=True)

    @staticmethod
    def getFromJid(jid):
        q = db.GqlQuery("SELECT * FROM XmppUser WHERE jid = :1", jid)
        return q.get()
