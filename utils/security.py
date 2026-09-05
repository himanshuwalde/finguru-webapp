import streamlit as st
from cryptography.fernet import Fernet

# Initialize the cipher with your secret key
def get_cipher():
    key = st.secrets["ENCRYPTION_KEY"].encode()
    return Fernet(key)

def encrypt_data(plain_text):
    if not plain_text: return ""
    cipher = get_cipher()
    # Encrypts the string into a secure token
    return cipher.encrypt(plain_text.encode()).decode()

def decrypt_data(cipher_text):
    if not cipher_text: return ""
    try:
        cipher = get_cipher()
        # Decrypts the token back into readable text
        return cipher.decrypt(cipher_text.encode()).decode()
    except Exception:
        # If decryption fails (e.g., bad key), return a masked string
        return "********"