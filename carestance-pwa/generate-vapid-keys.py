from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


private_key = ec.generate_private_key(ec.SECP256R1())
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

print("Store this value as VAPID_PRIVATE_KEY in the backend environment:")
print(private_pem.decode("ascii"))
