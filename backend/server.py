from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
import base64
import io
from PIL import Image
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Fraud detection system prompt
FRAUD_DETECTION_PROMPT = """You are FraudGPT, an expert AI assistant specialized in fraud detection and scam prevention. Your primary role is to help users identify potential scams, fraudulent activities, and suspicious communications.

Key capabilities:
1. Analyze text messages, emails, and communications for fraud indicators
2. Examine images for common scam patterns (fake websites, phishing attempts, suspicious QR codes, etc.)
3. Provide detailed explanations of why something might be fraudulent
4. Offer protective measures and advice
5. Educate users about common scam tactics

When analyzing content:
- Look for red flags like urgent language, requests for personal information, suspicious links, poor grammar/spelling
- Check for common scam patterns (romance scams, investment scams, tech support scams, etc.)
- Examine images for fake websites, suspicious QR codes, or fraudulent documents
- Provide confidence levels (High Risk, Medium Risk, Low Risk, Legitimate)
- Always explain your reasoning clearly

Be helpful, educational, and protective while being careful not to create false positives. If you're unsure, recommend seeking additional verification."""

# Models
class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    image_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New Chat"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ChatRequest(BaseModel):
    session_id: str
    message: str
    image_base64: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    message_id: str

# Helper function to process image
def process_image(image_base64: str) -> str:
    """Process base64 image and return it in proper format"""
    try:
        # Remove data URL prefix if present
        if image_base64.startswith('data:image'):
            image_base64 = image_base64.split(',')[1]
        
        # Decode and validate image
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large (max 1024x1024)
        max_size = 1024
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Convert back to base64
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode()
    
    except Exception as e:
        logging.error(f"Image processing error: {e}")
        raise HTTPException(status_code=400, detail="Invalid image format")

# Routes
@api_router.get("/")
async def root():
    return {"message": "FraudGPT API is running"}

@api_router.post("/chat/sessions", response_model=ChatSession)
async def create_chat_session():
    """Create a new chat session"""
    session = ChatSession()
    await db.chat_sessions.insert_one(session.dict())
    return session

@api_router.get("/chat/sessions", response_model=List[ChatSession])
async def get_chat_sessions():
    """Get all chat sessions"""
    sessions = await db.chat_sessions.find().sort("updated_at", -1).to_list(50)
    return [ChatSession(**session) for session in sessions]

@api_router.get("/chat/sessions/{session_id}/messages", response_model=List[ChatMessage])
async def get_chat_messages(session_id: str):
    """Get messages for a specific chat session"""
    messages = await db.chat_messages.find({"session_id": session_id}).sort("timestamp", 1).to_list(100)
    return [ChatMessage(**message) for message in messages]

@api_router.post("/chat/send", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message to FraudGPT"""
    try:
        # Validate session exists
        session = await db.chat_sessions.find_one({"id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Save user message
        user_message = ChatMessage(
            session_id=request.session_id,
            role="user",
            content=request.message,
            image_url=request.image_base64 if request.image_base64 else None
        )
        await db.chat_messages.insert_one(user_message.dict())
        
        # Initialize Gemini chat
        chat = LlmChat(
            api_key=os.environ['GEMINI_API_KEY'],
            session_id=request.session_id,
            system_message=FRAUD_DETECTION_PROMPT
        ).with_model("gemini", "gemini-2.0-flash")
        
        # Prepare user message for Gemini
        gemini_message = UserMessage(text=request.message)
        
        # Add image if provided
        if request.image_base64:
            processed_image = process_image(request.image_base64)
            image_content = ImageContent(image_base64=processed_image)
            gemini_message.file_contents = [image_content]
        
        # Get response from Gemini
        ai_response = await chat.send_message(gemini_message)
        
        # Save assistant response
        assistant_message = ChatMessage(
            session_id=request.session_id,
            role="assistant",
            content=ai_response
        )
        await db.chat_messages.insert_one(assistant_message.dict())
        
        # Update session timestamp
        await db.chat_sessions.update_one(
            {"id": request.session_id},
            {"$set": {"updated_at": datetime.utcnow()}}
        )
        
        return ChatResponse(
            response=ai_response,
            session_id=request.session_id,
            message_id=assistant_message.id
        )
        
    except Exception as e:
        logging.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@api_router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session and all its messages"""
    await db.chat_sessions.delete_one({"id": session_id})
    await db.chat_messages.delete_many({"session_id": session_id})
    return {"message": "Session deleted successfully"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()