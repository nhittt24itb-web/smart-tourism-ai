import hashlib
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from backend.database import get_db
from backend import models

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    email: str
    name: str = None
    avatar_url: str = None

# Hàm băm mật khẩu bằng SHA-256 + Salt (chuẩn an toàn, không xung đột bcrypt/passlib)
def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return f"{salt}${hashed}"

def verify_password(plain_password: str, stored_password: str) -> bool:
    try:
        if "$" in stored_password:
            salt, hashed = stored_password.split("$", 1)
            check = hashlib.sha256((plain_password + salt).encode('utf-8')).hexdigest()
            return check == hashed
        return plain_password == stored_password
    except Exception:
        return False

# 1. API ĐĂNG KÝ
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được sử dụng!"
        )

    full_name_val = user_in.full_name.strip() if user_in.full_name else user_in.email.split('@')[0]

    try:
        new_user = models.User(
            full_name=full_name_val,
            email=user_in.email,
            password=hash_password(user_in.password),
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi cơ sở dữ liệu: {str(e)}"
        )

    return {
        "message": "Đăng ký thành công!",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "full_name": new_user.full_name
        }
    }

# 2. API ĐĂNG NHẬP
@router.post("/login")
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác!"
        )

    if not verify_password(user_in.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác!"
        )

    return {
        "access_token": f"token_user_{user.id}",
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name or user.email.split('@')[0],
            "avatar_url": user.avatar_url
        }
    }

# 3. API ĐĂNG NHẬP GOOGLE (XỬ LÝ LỖI 404)
@router.post("/google")
def login_with_google(data: GoogleLoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        name_val = data.name if data.name else data.email.split('@')[0]
        user = models.User(
            email=data.email,
            full_name=name_val,
            password=hash_password("GOOGLE_DEFAULT_PWD"),
            avatar_url=data.avatar_url,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "access_token": f"token_user_{user.id}",
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name,
            "avatar_url": user.avatar_url
        }
    }