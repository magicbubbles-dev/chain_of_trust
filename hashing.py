import secrets

def generate_unique_key():
    return secrets.token_urlsafe(16)  # ~22 char safe string

