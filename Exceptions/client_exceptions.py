class WrongKeyEntered(Exception):
    def __str__(self):
        return """Wrong key was entered by user, and key field non-empty!"""
