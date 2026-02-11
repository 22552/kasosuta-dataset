import streamlit as st
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import os
import base64

st.title("暗号")

# -------------------------
# 🔑 鍵生成
# -------------------------
if st.button("新しい鍵ペア生成"):
    private_key = ec.generate_private_key(ec.SECP256R1())
    st.session_state.private_key = private_key

    public_key = private_key.public_key()

    # 秘密鍵PEM
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # 圧縮公開鍵
    compressed_pub = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.CompressedPoint
    )

    short_pub = base64.b64encode(compressed_pub).decode()
    st.info("注意！秘密鍵は-----BEGIN PRIVATE KEY-----などの囲みも含みます。")
    st.text_area("秘密鍵（保存しろ）", priv_pem.decode(), height=200)
    st.text_input("短い公開鍵（これ渡せ）", short_pub)

# -------------------------
# 🔐 秘密鍵読み込み
# -------------------------
st.subheader("既存の秘密鍵を読み込む")

priv_input = st.text_area("秘密鍵PEMを貼る")

if st.button("秘密鍵セット"):
    try:
        clean_key = priv_input.strip().encode()

        private_key = serialization.load_pem_private_key(
            clean_key,
            password=None,
        )

        st.session_state.private_key = private_key

        # 公開鍵復元
        public_key = private_key.public_key()

        # 圧縮公開鍵
        compressed_pub = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.CompressedPoint
        )

        short_pub = base64.b64encode(compressed_pub).decode()

        st.success("読み込み成功")
        st.text_input("復元された短い公開鍵", short_pub)

    except Exception as e:
        st.error(f"読み込み失敗: {e}")

# -------------------------
# 🔓 暗号 / 復号
# -------------------------
st.subheader("暗号 / 復号")

peer_short_pub = st.text_input("相手の短い公開鍵")

plaintext = st.text_input("暗号化するテキスト")

def derive_shared_key(private_key, peer_compressed_b64):
    peer_bytes = base64.b64decode(peer_compressed_b64)
    peer_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(),
        peer_bytes
    )

    shared_key = private_key.exchange(ec.ECDH(), peer_public_key)

    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"handshake data",
    ).derive(shared_key)

    return derived_key

if st.button("暗号化"):
    if "private_key" not in st.session_state:
        st.error("秘密鍵セットして")
    else:
        try:
            key = derive_shared_key(st.session_state.private_key, peer_short_pub)

            iv = os.urandom(16)
            cipher = Cipher(algorithms.AES(key), modes.CFB(iv))
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()

            result = base64.b64encode(iv + ciphertext).decode()
            st.text_area("暗号文", result)

        except Exception:
            st.error("暗号化失敗")

cipher_input = st.text_area("復号する暗号文")

if st.button("復号"):
    if "private_key" not in st.session_state:
        st.error("秘密鍵セットして")
    else:
        try:
            key = derive_shared_key(st.session_state.private_key, peer_short_pub)

            raw = base64.b64decode(cipher_input)
            iv = raw[:16]
            ciphertext = raw[16:]

            cipher = Cipher(algorithms.AES(key), modes.CFB(iv))
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(ciphertext) + decryptor.finalize()

            st.success("復号結果: " + decrypted.decode())

        except Exception:
            st.error("復号失敗")
