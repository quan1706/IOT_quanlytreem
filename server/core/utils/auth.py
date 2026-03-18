import jwt
import time
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import base64


class AuthToken:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()  # Chuyển đổi sang byte
        # Lấy khóa mã hóa độ dài cố định từ khóa bí mật (32 byte cho AES-256)
        self.encryption_key = self._derive_key(32)

    def _derive_key(self, length: int) -> bytes:
        """Lấy khóa có độ dài cố định"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        # Sử dụng giá trị muối cố định (trong môi trường sản xuất thực tế nên sử dụng muối ngẫu nhiên)
        salt = b"fixed_salt_placeholder"  # Môi trường sản xuất nên chuyển sang tạo ngẫu nhiên
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        return kdf.derive(self.secret_key)

    def _encrypt_payload(self, payload: dict) -> str:
        """Sử dụng AES-GCM để mã hóa toàn bộ nội dung (payload)"""
        # Chuyển đổi payload thành chuỗi JSON
        payload_json = json.dumps(payload)

        # Tạo IV ngẫu nhiên
        iv = os.urandom(12)
        # Tạo bộ mã hóa
        cipher = Cipher(
            algorithms.AES(self.encryption_key),
            modes.GCM(iv),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()
 
        # Mã hóa và tạo thẻ (tag)
        ciphertext = encryptor.update(payload_json.encode()) + encryptor.finalize()
        tag = encryptor.tag
 
        # Kết hợp IV + Bản mã + Thẻ
        encrypted_data = iv + ciphertext + tag
        return base64.urlsafe_b64encode(encrypted_data).decode()

    def _decrypt_payload(self, encrypted_data: str) -> dict:
        """Giải mã payload được mã hóa bằng AES-GCM"""
        # Giải mã Base64
        data = base64.urlsafe_b64decode(encrypted_data.encode())
        # Tách các thành phần
        iv = data[:12]
        tag = data[-16:]
        ciphertext = data[12:-16]
 
        # Tạo bộ giải mã
        cipher = Cipher(
            algorithms.AES(self.encryption_key),
            modes.GCM(iv, tag),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()

        # Giải mã
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return json.loads(plaintext.decode())

    def generate_token(self, device_id: str) -> str:
        """
        Tạo JWT token
        :param device_id: ID thiết bị
        :return: Chuỗi JWT token
        """
        # Thiết lập thời gian hết hạn là 1 giờ sau
        expire_time = datetime.now(timezone.utc) + timedelta(hours=1)
 
        # Tạo payload gốc
        payload = {"device_id": device_id, "exp": expire_time.timestamp()}
 
        # Mã hóa toàn bộ payload
        encrypted_payload = self._encrypt_payload(payload)
 
        # Tạo payload bên ngoài, bao gồm dữ liệu đã mã hóa
        outer_payload = {"data": encrypted_payload}
 
        # Sử dụng JWT để mã hóa
        token = jwt.encode(outer_payload, self.secret_key, algorithm="HS256")
        return token

    def verify_token(self, token: str) -> Tuple[bool, Optional[str]]:
        """
        Xác minh token
        :param token: Chuỗi JWT token
        :return: (Có hiệu lực hay không, ID thiết bị)
        """
        try:
            # Trước tiên xác minh JWT bên ngoài (chữ ký và thời gian hết hạn)
            outer_payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
 
            # Giải mã payload bên trong
            inner_payload = self._decrypt_payload(outer_payload["data"])
 
            # Kiểm tra lại thời gian hết hạn (Xác minh kép)
            if inner_payload["exp"] < time.time():
                return False, None

            return True, inner_payload["device_id"]

        except jwt.InvalidTokenError:
            return False, None
        except json.JSONDecodeError:
            return False, None
        except Exception as e:  # Bắt các lỗi khả nghi khác
            print(f"Token verification failed: {str(e)}")
            return False, None
