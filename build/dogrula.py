import base64, sys
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

dosya = sys.argv[1] if len(sys.argv) > 1 else "TürKod IDE.exe"

pub = serialization.load_pem_public_key(open("turkod_public.pem", "rb").read())
imza = base64.b64decode(open(dosya + ".sig", "rb").read())
veri = open(dosya, "rb").read()

try:
    pub.verify(
        imza, veri,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    print("İmza geçerli: dosya oynanmamış.")
except Exception:
    print("İmza geçersiz: dosyayı kullanma!")
