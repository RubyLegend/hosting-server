from .. import ALLOWED_PREVIEW_EXTENSIONS
import os
from ..database.logos import CompanyLogo

def allowed_logo_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_PREVIEW_EXTENSIONS


def get_unique_filepath_logo(filepath, session):
    """Generates a unique filename by appending a counter if necessary."""
    base, ext = os.path.splitext(filepath)
    counter = 1

    while True:
        existing_media = session.query(CompanyLogo).filter_by(LogoPath=filepath).first()
        if not existing_media:
            return filepath

        filepath = f"{base}({counter}){ext}"
        counter += 1

