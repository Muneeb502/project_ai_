from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import json
import logging


from database_models import *
from agents_system import FrontlineAgentSystem, OfflineModeHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Frontline Worker Support AI",
    description="Multi-agent system for frontline worker and citizen support",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
create_tables()

# WebSocket manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.case_subscribers: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    def subscribe_to_case(self, case_id: int, websocket: WebSocket):
        if case_id not in self.case_subscribers:
            self.case_subscribers[case_id] = []
        self.case_subscribers[case_id].append(websocket)
    
    async def send_case_update(self, case_id: int, message: dict):
        if case_id in self.case_subscribers:
            for connection in self.case_subscribers[case_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    await self.disconnect(connection)

manager = ConnectionManager()

# Pydantic models for API
class CitizenCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None

class CaseCreate(BaseModel):
    citizen_id: int
    title: str
    description: str

class CaseResponse(BaseModel):
    id: int
    title: str
    description: str
    urgency: str
    status: str
    created_at: datetime
    citizen_name: str
    assigned_service: Optional[str] = None
    appointment_time: Optional[datetime] = None

class ServiceResponse(BaseModel):
    id: int
    name: str
    type: str
    department: str
    location: str
    is_emergency: bool
    capacity_per_hour: int

class DashboardStats(BaseModel):
    total_cases: int
    pending_cases: int
    completed_cases: int
    average_processing_time: float
    services_utilization: Dict[str, float]

# Dependency to get database session
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize agent system
def get_agent_system(db: Session = Depends(get_db_session)):
    return FrontlineAgentSystem(db)

# API Endpoints

@app.get("/")
async def root():
    return {"message": "Frontline Worker Support AI System", "version": "1.0.0"}

# Citizen Management
@app.post("/api/citizens/", response_model=dict)
async def create_citizen(citizen: CitizenCreate, db: Session = Depends(get_db_session)):
    """Create a new citizen"""
    # Check if citizen already exists
    existing = db.query(Citizen).filter(Citizen.email == citizen.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Citizen with this email already exists")
    
    db_citizen = Citizen(**citizen.dict())
    db.add(db_citizen)
    db.commit()
    db.refresh(db_citizen)
    
    return {"id": db_citizen.id, "message": "Citizen created successfully"}

@app.get("/api/citizens/{citizen_id}")
async def get_citizen(citizen_id: int, db: Session = Depends(get_db_session)):
    """Get citizen details"""
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")
    return citizen

# Case Management
@app.post("/api/cases/", response_model=dict)
async def submit_case(
    case: CaseCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    agent_system: FrontlineAgentSystem = Depends(get_agent_system)
):
    """Submit a new case and trigger agent processing"""
    # Verify citizen exists
    citizen = db.query(Citizen).filter(Citizen.id == case.citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")
    
    # Create case
    db_case = Case(**case.dict())
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    
    # Trigger agent processing in background
    background_tasks.add_task(process_case_async, db_case.id, agent_system, db)
    
    return {"case_id": db_case.id, "message": "Case submitted successfully", "status": "processing"}

async def process_case_async(case_id: int, agent_system: FrontlineAgentSystem, db: Session):
    """Process case through agent system and send real-time updates"""
    try:
        result = await agent_system.process_case(case_id)
        
        # Send real-time update
        await manager.send_case_update(case_id, {
            "type": "case_processed",
            "case_id": case_id,
            "result": result
        })
        
    except Exception as e:
        logger.error(f"Error processing case {case_id}: {str(e)}")
        await manager.send_case_update(case_id, {
            "type": "case_error",
            "case_id": case_id,
            "error": str(e)
        })

@app.get("/api/cases/{case_id}")
async def get_case(case_id: int, db: Session = Depends(get_db_session)):
    """Get case details with full information"""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Get related data
    citizen = db.query(Citizen).filter(Citizen.id == case.citizen_id).first()
    service = None
    if case.assigned_service_id:
        service = db.query(Service).filter(Service.id == case.assigned_service_id).first()
    
    appointment = db.query(Appointment).filter(Appointment.case_id == case_id).first()
    updates = db.query(CaseUpdate).filter(CaseUpdate.case_id == case_id).order_by(CaseUpdate.created_at).all()
    
    return {
        "id": case.id,
        "title": case.title,
        "description": case.description,
        "urgency": case.urgency.value if case.urgency else "medium",
        "status": case.status.value,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "citizen": {
            "id": citizen.id,
            "name": citizen.name,
            "email": citizen.email,
            "phone": citizen.phone
        },
        "assigned_service": {
            "id": service.id,
            "name": service.name,
            "location": service.location,
            "contact": service.contact_info
        } if service else None,
        "appointment": {
            "id": appointment.id,
            "scheduled_time": appointment.scheduled_time,
            "duration_minutes": appointment.duration_minutes,
            "confirmation_sent": appointment.confirmation_sent
        } if appointment else None,
        "updates": [{
            "id": update.id,
            "message": update.message,
            "type": update.update_type,
            "agent": update.agent_type,
            "created_at": update.created_at
        } for update in updates]
    }

@app.get("/api/cases/", response_model=List[CaseResponse])
async def list_cases(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """List cases with filtering options"""
    query = db.query(Case).join(Citizen)
    
    if status:
        query = query.filter(Case.status == CaseStatus(status))
    if urgency:
        query = query.filter(Case.urgency == UrgencyLevel(urgency))
    
    cases = query.offset(skip).limit(limit).all()
    
    result = []
    for case in cases:
        service_name = None
        appointment_time = None
        
        if case.assigned_service_id:
            service = db.query(Service).filter(Service.id == case.assigned_service_id).first()
            service_name = service.name if service else None
        
        appointment = db.query(Appointment).filter(Appointment.case_id == case.id).first()
        if appointment:
            appointment_time = appointment.scheduled_time
        
        result.append(CaseResponse(
            id=case.id,
            title=case.title,
            description=case.description,
            urgency=case.urgency.value if case.urgency else "medium",
            status=case.status.value,
            created_at=case.created_at,
            citizen_name=case.citizen.name,
            assigned_service=service_name,
            appointment_time=appointment_time
        ))
    
    return result

# Service Management
@app.get("/api/services/", response_model=List[ServiceResponse])
async def list_services(db: Session = Depends(get_db_session)):
    """List all available services"""
    services = db.query(Service).all()
    return [ServiceResponse(
        id=service.id,
        name=service.name,
        type=service.type.value,
        department=service.department,
        location=service.location,
        is_emergency=service.is_emergency,
        capacity_per_hour=service.capacity_per_hour
    ) for service in services]

@app.post("/api/services/")
async def create_service(service_data: dict, db: Session = Depends(get_db_session)):
    """Create a new service (for admin use)"""
    service = Service(**service_data)
    db.add(service)
    db.commit()
    db.refresh(service)
    return {"id": service.id, "message": "Service created successfully"}

# Dashboard and Analytics
@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db_session)):
    """Get dashboard statistics"""
    total_cases = db.query(Case).count()
    pending_cases = db.query(Case).filter(
        Case.status.in_([CaseStatus.SUBMITTED, CaseStatus.TRIAGED, CaseStatus.ASSIGNED])
    ).count()
    completed_cases = db.query(Case).filter(Case.status == CaseStatus.COMPLETED).count()
    
    # Calculate average processing time (simplified)
    avg_processing_time = 45.5  # In practice, calculate from actual data
    
    # Service utilization (simplified)
    services_utilization = {}
    services = db.query(Service).all()
    for service in services:
        case_count = db.query(Case).filter(Case.assigned_service_id == service.id).count()
        services_utilization[service.name] = min(case_count / service.capacity_per_hour * 100, 100)
    
    return DashboardStats(
        total_cases=total_cases,
        pending_cases=pending_cases,
        completed_cases=completed_cases,
        average_processing_time=avg_processing_time,
        services_utilization=services_utilization
    )

@app.get("/api/dashboard/metrics")
async def get_system_metrics(db: Session = Depends(get_db_session)):
    """Get detailed system metrics"""
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    
    metrics = db.query(SystemMetrics).filter(SystemMetrics.date >= yesterday).all()
    
    return {
        "daily_metrics": [{
            "service_id": metric.service_id,
            "date": metric.date,
            "demand_count": metric.demand_count,
            "capacity_used": metric.capacity_used,
            "avg_wait_time": metric.avg_wait_time
        } for metric in metrics]
    }

# Offline Mode Support
@app.post("/api/cases/offline")
async def submit_case_offline(case_data: dict, db: Session = Depends(get_db_session)):
    """Submit case in offline/degraded mode"""
    offline_handler = OfflineModeHandler(db)
    result = await offline_handler.process_case_offline(case_data)
    
    return {
        "message": "Case processed in offline mode",
        "recommendation": result,
        "next_steps": "Please visit service center or call when connection restored"
    }

# WebSocket endpoint for real-time updates
@app.websocket("/ws/{case_id}")
async def websocket_endpoint(websocket: WebSocket, case_id: int):
    await manager.connect(websocket)
    manager.subscribe_to_case(case_id, websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

# Initialize sample data
@app.on_event("startup")
async def startup_event():
    """Initialize sample data on startup"""
    db = SessionLocal()
    try:
        # Check if data already exists
        if db.query(Service).first():
            return
        
        # Create sample services
        services = [
            Service(
                name="General Hospital Emergency",
                type=ServiceType.MEDICAL,
                department="Emergency Medicine",
                location="123 Medical Center Dr",
                capacity_per_hour=20,
                contact_info="555-0123",
                is_emergency=True
            ),
            Service(
                name="Community Health Clinic",
                type=ServiceType.MEDICAL,
                department="General Practice",
                location="456 Community Ave",
                capacity_per_hour=15,
                contact_info="555-0124",
                is_emergency=False
            ),
            Service(
                name="Emergency Response Unit",
                type=ServiceType.EMERGENCY,
                department="Emergency Services",
                location="789 Safety Blvd",
                capacity_per_hour=10,
                contact_info="911",
                is_emergency=True
            ),
            Service(
                name="Social Services Office",
                type=ServiceType.SOCIAL,
                department="Social Welfare",
                location="321 Support St",
                capacity_per_hour=12,
                contact_info="555-0125",
                is_emergency=False
            ),
            Service(
                name="City Administration",
                type=ServiceType.ADMINISTRATIVE,
                department="Administrative Services",
                location="654 City Hall",
                capacity_per_hour=25,
                contact_info="555-0126",
                is_emergency=False
            )
        ]
        
        for service in services:
            db.add(service)
        
        # Create sample citizens
        citizens = [
            Citizen(
                name="John Doe",
                email="john.doe@example.com",
                phone="555-1001",
                address="123 Main St",
                emergency_contact="Jane Doe - 555-1002"
            ),
            Citizen(
                name="Sarah Smith",
                email="sarah.smith@example.com",
                phone="555-1003",
                address="456 Oak Ave",
                emergency_contact="Mike Smith - 555-1004"
            ),
            Citizen(
                name="Robert Johnson",
                email="robert.johnson@example.com",
                phone="555-1005",
                address="789 Pine St",
                emergency_contact="Lisa Johnson - 555-1006"
            )
        ]
        
        for citizen in citizens:
            db.add(citizen)
        
        db.commit()
        logger.info("Sample data initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing sample data: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)