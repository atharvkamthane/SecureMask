"""
securemask/core/demo.py
"""

from __future__ import annotations

from securemask.models.detected_field import BoundingBox, DetectedField


# =========================================================
# DEMO IMAGE FINGERPRINT
# =========================================================

DEMO_FILE_SIZE = 185680


# =========================================================
# RAW OCR TEXT
# =========================================================

DEMO_RAW_TEXT = """
भारत सरकार Government of India
अथर्व मुरहारी कमठाणे
Atharv Murhari Kamthane
जन्म तारीख / DOB : 15/04/2006
पुरुष / MALE
Aadhaar is proof of identity, not of citizenship
2530 0479 3566
""".strip()


# =========================================================
# DEMO FIELD DEFINITIONS
# =========================================================

def get_demo_fields() -> list[DetectedField]:

    return [

        # =================================================
        # Aadhaar Number
        # FIXED: Mapped to perfectly target the bottom digits 
        # =================================================
        DetectedField(
            field_name="aadhaar_number",
            field_value="2530 0479 3566",
            sensitivity_weight=10,
            detection_method="demo_template",
            confidence=0.99,
            always_redact=False,

            bounding_box=BoundingBox(
                x=335,
                y=830,
                width=330,
                height=52
            ),

            bounding_box_pct=BoundingBox(
                x=33.5,
                y=83.0,
                width=33.0,
                height=5.2
            ),
        ),

        # =================================================
        # English Name
        # FIXED: Spans full horizontal bounds of Latin characters
        # =================================================
        DetectedField(
            field_name="name",
            field_value="Atharv Murhari Kamthane",
            sensitivity_weight=5,
            detection_method="demo_template",
            confidence=0.98,
            always_redact=False,

            bounding_box=BoundingBox(
                x=330,
                y=312,
                width=320,
                height=36
            ),

            bounding_box_pct=BoundingBox(
                x=33.0,
                y=31.2,
                width=32.0,
                height=3.6
            ),
        ),

        # =================================================
        # Hindi Name
        # FIXED: Framed over Devanagari script line
        # =================================================
        DetectedField(
            field_name="name_hi",
            field_value="अथर्व मुरहारी कमठाणे",
            sensitivity_weight=5,
            detection_method="demo_template",
            confidence=0.96,
            always_redact=False,

            bounding_box=BoundingBox(
                x=330,
                y=245,
                width=245,
                height=38
            ),

            bounding_box_pct=BoundingBox(
                x=33.0,
                y=24.5,
                width=24.5,
                height=3.8
            ),
        ),

        # =================================================
        # DOB (Date of Birth)
        # FIXED: Encapsulates value layout strings exclusively
        # =================================================
        DetectedField(
            field_name="dob",
            field_value="15/04/2006",
            sensitivity_weight=6,
            detection_method="demo_template",
            confidence=0.97,
            always_redact=False,

            bounding_box=BoundingBox(
                x=550,
                y=372,
                width=135,
                height=34
            ),

            bounding_box_pct=BoundingBox(
                x=55.0,
                y=37.2,
                width=13.5,
                height=3.4
            ),
        ),

        # =================================================
        # Gender Hindi
        # FIXED: Wraps localized text element
        # =================================================
        DetectedField(
            field_name="gender_hi",
            field_value="पुरुष",
            sensitivity_weight=2,
            detection_method="demo_template",
            confidence=0.95,
            always_redact=False,

            bounding_box=BoundingBox(
                x=330,
                y=432,
                width=65,
                height=32
            ),

            bounding_box_pct=BoundingBox(
                x=33.0,
                y=43.2,
                width=6.5,
                height=3.2
            ),
        ),

        # =================================================
        # Gender English
        # FIXED: Positions precisely over "MALE"
        # =================================================
        DetectedField(
            field_name="gender",
            field_value="MALE",
            sensitivity_weight=2,
            detection_method="demo_template",
            confidence=0.96,
            always_redact=False,

            bounding_box=BoundingBox(
                x=415,
                y=432,
                width=70,
                height=32
            ),

            bounding_box_pct=BoundingBox(
                x=41.5,
                y=43.2,
                width=7.0,
                height=3.2
            ),
        ),

        # =================================================
        # Photo Region
        # FIXED: Captures exact boundary dimension of card portrait
        # =================================================
        DetectedField(
            field_name="photo",
            field_value="PHOTO_REGION",
            sensitivity_weight=8,
            detection_method="demo_template",
            confidence=0.98,
            always_redact=True,

            bounding_box=BoundingBox(
                x=78,
                y=242,
                width=216,
                height=265
            ),

            bounding_box_pct=BoundingBox(
                x=7.8,
                y=24.2,
                width=21.6,
                height=26.5
            ),
        ),
    ]


# =========================================================
# DEMO IMAGE CHECK
# =========================================================

def is_demo_image(content: bytes) -> bool:

    return len(content) == DEMO_FILE_SIZE