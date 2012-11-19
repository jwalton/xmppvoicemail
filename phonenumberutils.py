import re

# Adapted from http://blog.stevenlevithan.com/archives/validate-phone-number
_phoneNumberRegex = re.compile(r"^\+?1?[ -]?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})$")
_e164Regex = re.compile(r"^\+(?:[0-9] ?){6,14}[0-9]$")

def stripNumber(number):
    """ Strips all non-digits from a phone number. """
    return re.sub(r'[^0-9]', "", number)

def toPrettyNumber(phoneNumber):
    """ Converts a number to nicely formatted number. """
    match = _phoneNumberRegex.match(phoneNumber)
    if match:
        return "(" + match.group(1) + ")" + match.group(2) + "-" + match.group(3)
    else:
        return phoneNumber

def toNormalizedNumber(phoneNumber):
    """ Returns a normalized E.164 phone number.
    
    The number returned will always have a leading "+", followed by a "1" for
    North American style numbers, followed by digits with no spaces.
    """
    normalizedNumber = stripNumber(phoneNumber)
    if len(normalizedNumber) == 10:
        normalizedNumber = "1" + normalizedNumber
    return "+" + normalizedNumber

def validateNumber(phoneNumber):
    """ Returns True if 'phoneNumber' is a valid phone number, False otherwise. """
    answer = False
    match = _phoneNumberRegex.match(phoneNumber)
    if match:
        answer = True
    else:
        match = _e164Regex.match(phoneNumber)
        if match:
            answer = True
            
    return answer
