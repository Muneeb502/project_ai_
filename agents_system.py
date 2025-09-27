from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime, timedelta
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain.schema import Document
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import json
import asyncio
from sqlalchemy.orm import Session
from database_models import *

# State definition for the multi-agent system
class AgentState(TypedDict):
    case_id: int
    citizen_data: Dict[str, Any]
    case_description: str
    urgency_level: str
    assigned_service_id: Optional[int]
    appointment_details: Optional[Dict[str, Any]]
    messages: List[BaseMessage]
    agent_outputs: Dict[str, Any]
    current_status: str
    error_message: Optional[str]
    offline_mode: bool

# Pydantic models for tool inputs/outputs
class TriageInput(BaseModel):
    case_description: str
    citizen_info: Dict[str, Any]

class TriageOutput(BaseModel):
    urgency: str
    estimated_duration: int
    triage_notes: str
    recommended_service_type: str

class ServiceMatchInput(BaseModel):
    urgency: str
    service_type: str
    citizen_location: Optional[str] = None

class BookingInput(BaseModel):
    service_id: int
    preferred_time: Optional[str] = None
    duration_minutes: int = 30

# Database Tools
class DatabaseTool(BaseTool):
    name: str = "database_tool"
    description: str = "Tool for database operations"
    
    def __init__(self, db_session: Session):
        super().__init__()
        self.db_session = db_session
    
    def _run(self, query: str) -> str:
        # This would implement actual database queries
        pass

# Triage Agent
class TriageAgent:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.name = "triage_agent"
    
    async def analyze_case(self, state: AgentState) -> AgentState:
        """Analyze case urgency and requirements"""
        case_id = state["case_id"]
        case_description = state["case_description"]
        
        # Get case from database
        case = self.db_session.query(Case).filter(Case.id == case_id).first()
        if not case:
            state["error_message"] = "Case not found"
            return state
        
        # Simple rule-based triage (in production, this would use AI)
        urgency = self._determine_urgency(case_description)
        service_type = self._determine_service_type(case_description)
        estimated_duration = self._estimate_duration(case_description, urgency)
        
        # Update case in database
        case.urgency = UrgencyLevel(urgency)
        case.status = CaseStatus.TRIAGED
        case.triage_notes = f"Automated triage: {urgency} priority, {service_type} service needed"
        case.estimated_duration = estimated_duration
        
        # Add case update
        update = CaseUpdate(
            case_id=case_id,
            message=f"Case triaged as {urgency} priority requiring {service_type} service",
            update_type="triage",
            agent_type="triage"
        )
        self.db_session.add(update)
        self.db_session.commit()
        
        # Update state
        state["urgency_level"] = urgency
        state["current_status"] = "triaged"
        state["agent_outputs"]["triage"] = {
            "urgency": urgency,
            "service_type": service_type,
            "estimated_duration": estimated_duration,
            "notes": case.triage_notes
        }
        
        state["messages"].append(
            AIMessage(content=f"Triage completed: {urgency} priority case requiring {service_type} service")
        )
        
        return state
    
    def _determine_urgency(self, description: str) -> str:
        description_lower = description.lower()
        if any(word in description_lower for word in ["emergency", "urgent", "critical", "severe", "life-threatening"]):
            return "critical"
        elif any(word in description_lower for word in ["pain", "injury", "bleeding", "fever"]):
            return "high"
        elif any(word in description_lower for word in ["appointment", "consultation", "check-up"]):
            return "medium"
        else:
            return "low"
    
    def _determine_service_type(self, description: str) -> str:
        description_lower = description.lower()
        if any(word in description_lower for word in ["medical", "doctor", "hospital", "health", "pain", "injury"]):
            return "medical"
        elif any(word in description_lower for word in ["emergency", "police", "fire", "ambulance"]):
            return "emergency"
        elif any(word in description_lower for word in ["social", "welfare", "benefits", "housing"]):
            return "social"
        else:
            return "administrative"
    
    def _estimate_duration(self, description: str, urgency: str) -> int:
        if urgency == "critical":
            return 60
        elif urgency == "high":
            return 45
        elif urgency == "medium":
            return 30
        else:
            return 15

# Guidance Agent
class GuidanceAgent:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.name = "guidance_agent"
    
    async def match_service(self, state: AgentState) -> AgentState:
        """Match case to appropriate service"""
        urgency = state["urgency_level"]
        service_type = state["agent_outputs"]["triage"]["service_type"]
        
        # Find best matching service
        query = self.db_session.query(Service).filter(Service.type == ServiceType(service_type))
        
        if urgency in ["critical", "high"]:
            query = query.filter(Service.is_emergency == True)
        
        services = query.all()
        
        if not services:
            state["error_message"] = f"No available services for {service_type}"
            return state
        
        # Simple selection (in production, this would consider capacity, location, etc.)
        selected_service = services[0]
        
        # Update case
        case = self.db_session.query(Case).filter(Case.id == state["case_id"]).first()
        case.assigned_service_id = selected_service.id
        case.status = CaseStatus.ASSIGNED
        
        # Add update
        update = CaseUpdate(
            case_id=state["case_id"],
            message=f"Case assigned to {selected_service.name} at {selected_service.location}",
            update_type="assignment",
            agent_type="guidance"
        )
        self.db_session.add(update)
        self.db_session.commit()
        
        # Update state
        state["assigned_service_id"] = selected_service.id
        state["current_status"] = "assigned"
        state["agent_outputs"]["guidance"] = {
            "service_name": selected_service.name,
            "service_location": selected_service.location,
            "service_contact": selected_service.contact_info,
            "department": selected_service.department
        }
        
        state["messages"].append(
            AIMessage(content=f"Case assigned to {selected_service.name} in {selected_service.department}")
        )
        
        return state

# Booking Agent
class BookingAgent:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.name = "booking_agent"
    
    async def book_appointment(self, state: AgentState) -> AgentState:
        """Autonomously book appointment"""
        service_id = state["assigned_service_id"]
        case_id = state["case_id"]
        urgency = state["urgency_level"]
        estimated_duration = state["agent_outputs"]["triage"]["estimated_duration"]
        
        service = self.db_session.query(Service).filter(Service.id == service_id).first()
        if not service:
            state["error_message"] = "Service not found"
            return state
        
        # Calculate next available slot
        scheduled_time = self._find_next_slot(service, urgency)
        
        # Create appointment
        appointment = Appointment(
            case_id=case_id,
            service_id=service_id,
            scheduled_time=scheduled_time,
            duration_minutes=estimated_duration,
            notes=f"Auto-booked {urgency} priority appointment"
        )
        self.db_session.add(appointment)
        
        # Update case
        case = self.db_session.query(Case).filter(Case.id == case_id).first()
        case.status = CaseStatus.SCHEDULED
        
        # Add update
        update = CaseUpdate(
            case_id=case_id,
            message=f"Appointment scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')} at {service.name}",
            update_type="booking",
            agent_type="booking"
        )
        self.db_session.add(update)
        self.db_session.commit()
        
        # Update state
        state["appointment_details"] = {
            "service_name": service.name,
            "location": service.location,
            "scheduled_time": scheduled_time.isoformat(),
            "duration": estimated_duration,
            "contact": service.contact_info
        }
        state["current_status"] = "scheduled"
        state["agent_outputs"]["booking"] = state["appointment_details"]
        
        state["messages"].append(
            AIMessage(content=f"Appointment booked for {scheduled_time.strftime('%B %d, %Y at %I:%M %p')}")
        )
        
        return state
    
    def _find_next_slot(self, service: Service, urgency: str) -> datetime:
        """Find next available appointment slot"""
        now = datetime.utcnow()
        
        # For critical cases, schedule within 2 hours
        if urgency == "critical":
            return now + timedelta(hours=1)
        elif urgency == "high":
            return now + timedelta(hours=4)
        elif urgency == "medium":
            return now + timedelta(days=1)
        else:
            return now + timedelta(days=3)

# Follow-up Agent
class FollowUpAgent:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.name = "followup_agent"
    
    async def send_confirmation(self, state: AgentState) -> AgentState:
        """Send plain language confirmation to citizen"""
        appointment = state["appointment_details"]
        citizen_data = state["citizen_data"]
        
        # Generate plain language confirmation
        confirmation_message = self._generate_confirmation_message(appointment, citizen_data)
        
        # Update appointment confirmation status
        case_id = state["case_id"]
        appointment_record = self.db_session.query(Appointment).filter(
            Appointment.case_id == case_id
        ).first()
        
        if appointment_record:
            appointment_record.confirmation_sent = True
            self.db_session.commit()
        
        # Add update
        update = CaseUpdate(
            case_id=case_id,
            message="Confirmation sent to citizen",
            update_type="confirmation",
            agent_type="follow_up"
        )
        self.db_session.add(update)
        self.db_session.commit()
        
        # Update state
        state["agent_outputs"]["followup"] = {
            "confirmation_message": confirmation_message,
            "confirmation_sent": True
        }
        
        state["messages"].append(
            AIMessage(content="Confirmation message sent to citizen")
        )
        
        return state
    
    def _generate_confirmation_message(self, appointment: Dict, citizen_data: Dict) -> str:
        scheduled_time = datetime.fromisoformat(appointment["scheduled_time"])
        
        return f"""
        Hello {citizen_data.get('name', 'Citizen')},
        
        Your appointment has been successfully booked:
        
        📅 Date & Time: {scheduled_time.strftime('%A, %B %d, %Y at %I:%M %p')}
        🏥 Location: {appointment['service_name']} - {appointment['location']}
        ⏱️ Duration: {appointment['duration']} minutes
        📞 Contact: {appointment.get('contact', 'N/A')}
        
        Please bring:
        - Valid ID card
        - Any relevant medical documents
        - Insurance information (if applicable)
        
        If you need to reschedule, please contact us at least 2 hours in advance.
        
        Thank you for using our service!
        """

# Equity Oversight Agent
class EquityOversightAgent:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.name = "equity_agent"
    
    async def track_metrics(self, state: AgentState) -> AgentState:
        """Track service demand and generate insights"""
        service_id = state.get("assigned_service_id")
        
        if service_id:
            # Update metrics
            today = datetime.utcnow().date()
            metric = self.db_session.query(SystemMetrics).filter(
                SystemMetrics.service_id == service_id,
                SystemMetrics.date >= today
            ).first()
            
            if not metric:
                metric = SystemMetrics(
                    service_id=service_id,
                    demand_count=1
                )
                self.db_session.add(metric)
            else:
                metric.demand_count += 1
            
            self.db_session.commit()
        
        state["agent_outputs"]["equity"] = {
            "metrics_updated": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return state

# Main Multi-Agent Workflow
class FrontlineAgentSystem:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.triage_agent = TriageAgent(db_session)
        self.guidance_agent = GuidanceAgent(db_session)
        self.booking_agent = BookingAgent(db_session)
        self.followup_agent = FollowUpAgent(db_session)
        self.equity_agent = EquityOversightAgent(db_session)
        
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """Create the multi-agent workflow using LangGraph"""
        workflow = StateGraph(AgentState)
        
        # Add nodes (agents)
        workflow.add_node("triage", self.triage_agent.analyze_case)
        workflow.add_node("guidance", self.guidance_agent.match_service)
        workflow.add_node("booking", self.booking_agent.book_appointment)
        workflow.add_node("followup", self.followup_agent.send_confirmation)
        workflow.add_node("equity", self.equity_agent.track_metrics)
        
        # Define the workflow edges
        workflow.set_entry_point("triage")
        workflow.add_edge("triage", "guidance")
        workflow.add_edge("guidance", "booking")
        workflow.add_edge("booking", "followup")
        workflow.add_edge("followup", "equity")
        workflow.add_edge("equity", END)
        
        return workflow.compile()
    
    async def process_case(self, case_id: int, offline_mode: bool = False) -> Dict[str, Any]:
        """Process a case through the multi-agent system"""
        # Get case and citizen data
        case = self.db_session.query(Case).filter(Case.id == case_id).first()
        if not case:
            return {"error": "Case not found"}
        
        citizen = self.db_session.query(Citizen).filter(Citizen.id == case.citizen_id).first()
        
        # Initialize state
        initial_state: AgentState = {
            "case_id": case_id,
            "citizen_data": {
                "name": citizen.name,
                "email": citizen.email,
                "phone": citizen.phone,
                "address": citizen.address
            },
            "case_description": case.description,
            "urgency_level": "",
            "assigned_service_id": None,
            "appointment_details": None,
            "messages": [HumanMessage(content=case.description)],
            "agent_outputs": {},
            "current_status": case.status.value,
            "error_message": None,
            "offline_mode": offline_mode
        }
        
        # Run the workflow
        try:
            final_state = await self.workflow.ainvoke(initial_state)
            return {
                "success": True,
                "case_id": case_id,
                "final_status": final_state["current_status"],
                "agent_outputs": final_state["agent_outputs"],
                "appointment_details": final_state.get("appointment_details"),
                "messages": [msg.content for msg in final_state["messages"]]
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "case_id": case_id
            }

# Offline/Degraded Mode Handler
class OfflineModeHandler:
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    async def process_case_offline(self, case_data: Dict) -> Dict[str, Any]:
        """Process case in degraded/offline mode with simplified logic"""
        # Simple rule-based processing without AI
        urgency = self._simple_triage(case_data["description"])
        service_type = self._simple_service_match(case_data["description"])
        
        return {
            "urgency": urgency,
            "recommended_service": service_type,
            "message": "Processed in offline mode with simplified logic",
            "next_steps": "Please visit the nearest service center or call when connection is restored"
        }
    
    def _simple_triage(self, description: str) -> str:
        emergency_keywords = ["emergency", "urgent", "critical", "severe"]
        if any(keyword in description.lower() for keyword in emergency_keywords):
            return "high"
        return "medium"
    
    def _simple_service_match(self, description: str) -> str:
        if any(word in description.lower() for word in ["medical", "health", "doctor"]):
            return "medical"
        return "general"