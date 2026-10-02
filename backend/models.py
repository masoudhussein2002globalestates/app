from typing import Literal, Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from datetime import date

Category = Literal['Rent', 'Vacation', 'Outings', 'Land']

class UserOut(BaseModel):
    user_id: str
    name: str
    email: str
    picture: str = ''

class PropertyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    title: str = Field(min_length=5, max_length=120)
    category: Category
    location: str = Field(min_length=2, max_length=120)
    country: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=30, max_length=8000)
    price: float = Field(gt=0, le=100000000000)
    bedrooms: int = Field(default=0, ge=0, le=100)
    guests: int = Field(default=1, ge=1, le=500)
    amenities: list[str] = Field(default_factory=list, max_length=30)
    images: list[str] = Field(min_length=1, max_length=12)
    contact_email: EmailStr
    size: str = Field(default='', max_length=80)
    status: Literal['active', 'paused'] = 'active'

    @field_validator('images')
    @classmethod
    def valid_images(cls, value):
        from urllib.parse import urlparse
        for image in value:
            if len(image) > 2000 or not (image.startswith('/api/media/') or (urlparse(image).scheme == 'https' and urlparse(image).hostname)):
                raise ValueError('Use an uploaded image or a valid HTTPS image URL')
        return value

    @field_validator('amenities')
    @classmethod
    def valid_amenities(cls, value):
        if any(not a.strip() or len(a) > 80 for a in value):
            raise ValueError('Amenities must be between 1 and 80 characters')
        return list(dict.fromkeys(a.strip() for a in value))

class PropertyOut(BaseModel):
    id: str
    host_id: str
    host_name: str
    title: str
    category: Category
    location: str
    country: str
    description: str
    price: float
    bedrooms: int
    guests: int
    amenities: list[str]
    images: list[str]
    size: str = ''
    listing_plan: str
    status: str
    is_sample: bool = False
    created_at: str

class PropertyList(BaseModel):
    properties: list[PropertyOut]
    total: int
    page: int
    pages: int

class BookingInput(BaseModel):
    property_id: str
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=500)

class CheckoutInput(BaseModel):
    property_id: str
    plan: Optional[Literal['Featured', 'Premium']] = None
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    guests: int = Field(default=1, ge=1, le=500)

class BookingOut(BaseModel):
    id: str
    property_id: str
    property_title: str
    host_id: str
    customer_name: str
    check_in: str
    check_out: str
    guests: int
    amount: float
    platform_fee: float
    host_payout: float
    payment_status: str
    payout_status: str
    stripe_session_id: str = ''
    payment_intent_id: str = ''
    transfer_id: str = ''
    created_at: str

class InquiryOut(BaseModel):
    id: str
    property_id: str
    property_title: str
    customer_name: str
    customer_email: str
    message: str
    created_at: str

class DashboardOut(BaseModel):
    properties: list[PropertyOut]
    bookings: list[BookingOut]
    inquiries: list[InquiryOut]
    revenue: float
    earnings: float
    pending_payouts: float
    transferred: float
    payout_onboarding: str