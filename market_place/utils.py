import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
import hmac
import hashlib
from django.conf import settings
import uuid
from PIL import Image, ImageDraw, ImageFont


def generate_qr_signature(ticket_uuid, event_uuid):
    message = f"{ticket_uuid}:{event_uuid}".encode()
    secret = settings.SECRET_KEY.encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:16]


def verify_qr_signature(ticket_uuid, event_uuid, signature):
    expected_signature = generate_qr_signature(ticket_uuid, event_uuid)
    return hmac.compare_digest(signature, expected_signature)


def generate_ticket_qr_code(ticket):
    # Generate signature
    signature = generate_qr_signature(str(ticket.id), str(ticket.event.id))
    
    # QR data format: ticket_uuid:event_uuid:signature
    qr_data = f"{ticket.id}:{ticket.event.id}:{signature}"
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create image with custom colors
    img = qr.make_image(fill_color="#0b66a8", back_color="white")
    
    # Convert to RGB if needed
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Save to BytesIO
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Generate filename
    filename = f"qr_{ticket.id}.png"
    
    # Save to ticket model
    ticket.qr_code = qr_data
    ticket.qr_code_image.save(filename, ContentFile(buffer.read()), save=True)
    
    return qr_data


def parse_qr_data(qr_data):
    try:
        parts = qr_data.split(':')
        if len(parts) != 3:
            return None, None, False
        
        ticket_uuid, event_uuid, signature = parts
        
        # Validate UUIDs
        uuid.UUID(ticket_uuid)
        uuid.UUID(event_uuid)
        
        # Verify signature
        is_valid = verify_qr_signature(ticket_uuid, event_uuid, signature)
        
        return ticket_uuid, event_uuid, is_valid
    except (ValueError, AttributeError):
        return None, None, False