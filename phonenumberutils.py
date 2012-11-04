import re

_phoneNumberRegex = re.compile(r"^(?:1)[- ]?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})$")

def stripNumber(number):
    return re.sub(r'[^0-9]', "", number)

def toPrettyNumber(phoneNumber):
    # Adapted from http://blog.stevenlevithan.com/archives/validate-phone-number
    match = _phoneNumberRegex.match(phoneNumber)
    if match:
        return "(" + match.group(1) + ")" + match.group(2) + "-" + match.group(3)
    else:
        return phoneNumber
