import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database_models import *
from agents_system import FrontlineAgentSystem

async def create_demo_data():
    """Create comprehensive demo data for testing the system"""
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Clear existing data
        db.query(CaseUpdate).delete()
        db.query(Appointment).delete()
        db.query(SystemMetrics).delete()
        db.query(Case).delete()
        db.query(Citizen).delete()
        db.query(Service).delete()
        db.commit()
        
        print("🗑️  Cleared existing data")
        
        # Create Services
        services = [
            Service(
                name="City General Hospital - Emergency",
                type=ServiceType.MEDICAL,
                department="Emergency Medicine",
                location="123 Medical Center Drive, Downtown",
                capacity_per_hour=25,
                contact_info="555-EMERGENCY (555-363-7436)",
                is_emergency=True
            ),
            Service(
                name="Community Health Clinic",
                type=ServiceType.MEDICAL,
                department="General Practice",
                location="456 Community Avenue, Midtown",
                capacity_per_hour=15,
                contact_info="555-HEALTH-1 (555-432-5841)",
                is_emergency=False
            ),
            Service(
                name="Specialized Medical Center",
                type=ServiceType.MEDICAL,
                department="Specialist Care",
                location="789 Specialist Road, Medical District",
                capacity_per_hour=12,
                contact_info="555-SPECIAL (555-773-2425)",
                is_emergency=False
            ),
            Service(
                name="Emergency Response Unit",
                type=ServiceType.EMERGENCY,
                department="Fire & Rescue",
                location="321 Safety Boulevard, City Center",
                capacity_per_hour=20,
                contact_info="911 or 555-FIRE-911",
                is_emergency=True
            ),
            Service(
                name="Police Department",
                type=ServiceType.EMERGENCY,
                department="Law Enforcement",
                location="654 Justice Street, Government Quarter",
                capacity_per_hour=30,
                contact_info="911 or 555-POLICE-1",
                is_emergency=True
            ),
            Service(
                name="Social Services Department",
                type=ServiceType.SOCIAL,
                department="Social Welfare",
                location="987 Support Street, Civic Center",
                capacity_per_hour=18,
                contact_info="555-SOCIAL (555-762-4251)",
                is_emergency=False
            ),
            Service(
                name="Housing Authority",
                type=ServiceType.SOCIAL,
                department="Housing Assistance",
                location="147 Housing Lane, Municipal Complex",
                capacity_per_hour=10,
                contact_info="555-HOUSING (555-468-7464)",
                is_emergency=False
            ),
            Service(
                name="City Administration Office",
                type=ServiceType.ADMINISTRATIVE,
                department="Municipal Services",
                location="258 City Hall Plaza, Government District",
                capacity_per_hour=25,
                contact_info="555-CITY-GOV (555-248-9468)",
                is_emergency=False
            ),
            Service(
                name="Department of Motor Vehicles",
                type=ServiceType.ADMINISTRATIVE,
                department="Vehicle Services",
                location="369 DMV Drive, Administrative Complex",
                capacity_per_hour=20,
                contact_info="555-DMV-INFO (555-368-4636)",
                is_emergency=False
            ),
            Service(
                name="Tax Assessment Office",
                type=ServiceType.ADMINISTRATIVE,
                department="Revenue Services",
                location="741 Revenue Road, Municipal Building",
                capacity_per_hour=15,
                contact_info="555-TAX-HELP (555-829-4357)",
                is_emergency=False
            )
        ]
        
        for service in services:
            db.add(service)
        
        db.commit()
        print("🏥 Created services")
        
        # Create Citizens
        citizens = [
            Citizen(
                name="John Doe",
                email="john.doe@email.com",
                phone="555-1001",
                address="123 Main Street, Residential Area",
                emergency_contact="Jane Doe - 555-1002"
            ),
            Citizen(
                name="Sarah Smith",
                email="sarah.smith@email.com",
                phone="555-1003",
                address="456 Oak Avenue, Suburbia",
                emergency_contact="Mike Smith - 555-1004"
            ),
            Citizen(
                name="Robert Johnson",
                email="robert.johnson@email.com",
                phone="555-1005",
                address="789 Pine Street, Downtown",
                emergency_contact="Lisa Johnson - 555-1006"
            ),
            Citizen(
                name="Emily Davis",
                email="emily.davis@email.com",
                phone="555-1007",
                address="321 Elm Drive, Uptown",
                emergency_contact="David Davis - 555-1008"
            ),
            Citizen(
                name="Michael Brown",
                email="michael.brown@email.com",
                phone="555-1009",
                address="654 Maple Lane, Westside",
                emergency_contact="Jennifer Brown - 555-1010"
            ),
            Citizen(
                name="Jessica Wilson",
                email="jessica.wilson@email.com",
                phone="555-1011",
                address="987 Cedar Court, Eastside",
                emergency_contact="James Wilson - 555-1012"
            ),
            Citizen(
                name="Christopher Taylor",
                email="chris.taylor@email.com",
                phone="555-1013",
                address="147 Birch Boulevard, Midtown",
                emergency_contact="Amanda Taylor - 555-1014"
            ),
            Citizen(
                name="Amanda Miller",
                email="amanda.miller@email.com",
                phone="555-1015",
                address="258 Spruce Street, Southside",
                emergency_contact="Christopher Miller - 555-1016"
            )
        ]
        
        for citizen in citizens:
            db.add(citizen)
        
        db.commit()
        print("👥 Created citizens")
        
        # Create Sample Cases with different scenarios
        sample_cases = [
            {
                "citizen_id": 1,
                "title": "Severe chest pain and shortness of breath",
                "description": "I'm experiencing severe chest pain that started an hour ago, along with difficulty breathing and sweating. This feels like it could be serious and I need immediate medical attention.",
                "expected_urgency": "critical",
                "expected_service": "medical"
            },
            {
                "citizen_id": 2,
                "title": "Car accident with minor injuries",
                "description": "I was involved in a minor car accident at the intersection of Main St and Oak Ave. I have some cuts and bruises but nothing seems broken. Need to file a police report and get medical clearance.",
                "expected_urgency": "high",
                "expected_service": "emergency"
            },
            {
                "citizen_id": 3,
                "title": "Annual health checkup appointment",
                "description": "I need to schedule my annual health checkup. It's been over a year since my last visit and I want to make sure everything is okay. Preferably next week if possible.",
                "expected_urgency": "low",
                "expected_service": "medical"
            },
            {
                "citizen_id": 4,
                "title": "Housing assistance application",
                "description": "I recently lost my job due to company downsizing and I'm struggling to make rent payments. I need information about emergency housing assistance programs and how to apply.",
                "expected_urgency": "medium",
                "expected_service": "social"
            },
            {
                "citizen_id": 5,
                "title": "Driver's license renewal",
                "description": "My driver's license expires next month and I need to renew it. I'd like to schedule an appointment at the DMV office and find out what documents I need to bring.",
                "expected_urgency": "low",
                "expected_service": "administrative"
            },
            {
                "citizen_id": 6,
                "title": "Domestic violence situation - need help",
                "description": "I'm in an unsafe domestic situation and need immediate help and guidance. I'm scared and don't know where to turn. Please help me find resources and safety options.",
                "expected_urgency": "critical",
                "expected_service": "emergency"
            },
            {
                "citizen_id": 7,
                "title": "High fever and persistent cough",
                "description": "I've had a high fever (102°F) for 3 days along with a persistent cough and body aches. I'm concerned it might be something serious and need to see a doctor soon.",
                "expected_urgency": "high",
                "expected_service": "medical"
            },
            {
                "citizen_id": 8,
                "title": "Property tax assessment appeal",
                "description": "I believe my property tax assessment is too high compared to similar properties in my neighborhood. I need to file an appeal and understand the process.",
                "expected_urgency": "low",
                "expected_service": "administrative"
            },
            {
                "citizen_id": 1,
                "title": "Food poisoning symptoms",
                "description": "I ate at a restaurant yesterday and now I'm experiencing severe nausea, vomiting, and diarrhea. I'm getting dehydrated and feel very weak.",
                "expected_urgency": "high",
                "expected_service": "medical"
            },
            {
                "citizen_id": 3,
                "title": "Unemployment benefits application",
                "description": "I was recently laid off from my job and need to apply for unemployment benefits. I need help understanding the process and what documentation is required.",
                "expected_urgency": "medium",
                "expected_service": "social"
            }
        ]
        
        cases = []
        for case_data in sample_cases:
            case = Case(
                citizen_id=case_data["citizen_id"],
                title=case_data["title"],
                description=case_data["description"],
                status=CaseStatus.SUBMITTED,
                created_at=datetime.utcnow() - timedelta(
                    hours=len(cases),  # Stagger creation times
                    minutes=len(cases) * 15
                )
            )
            cases.append(case)
            db.add(case)
        
        db.commit()
        print("📋 Created sample cases")
        
        # Process some cases through the agent system
        agent_system = FrontlineAgentSystem(db)
        
        processed_cases = []
        for i, case in enumerate(cases[:5]):  # Process first 5 cases
            print(f"🤖 Processing Case #{case.id}: {case.title}")
            
            try:
                result = await agent_system.process_case(case.id)
                processed_cases.append(result)
                print(f"   ✅ Processed successfully - Status: {result.get('final_status', 'unknown')}")
                
                # Add some delay between processing
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ Error processing case: {str(e)}")
        
        # Create some system metrics
        services_list = db.query(Service).all()
        for service in services_list:
            # Create metrics for today and yesterday
            for days_ago in [0, 1]:
                date = datetime.utcnow() - timedelta(days=days_ago)
                
                metric = SystemMetrics(
                    service_id=service.id,
                    date=date,
                    demand_count=5 + (days_ago * 3),  # More demand yesterday
                    capacity_used=60.0 + (days_ago * 10),  # Higher utilization yesterday
                    avg_wait_time=25.0 - (days_ago * 5),  # Improved wait time
                    satisfaction_score=4.2 + (days_ago * 0.3)  # Improved satisfaction
                )
                db.add(metric)
        
        db.commit()
        print("📊 Created system metrics")
        
        # Summary
        total_citizens = db.query(Citizen).count()
        total_services = db.query(Service).count()
        total_cases = db.query(Case).count()
        processed_count = len([c for c in processed_cases if c.get('success')])
        
        print("\n" + "="*50)
        print("🎉 DEMO DATA SETUP COMPLETE!")
        print("="*50)
        print(f"👥 Citizens created: {total_citizens}")
        print(f"🏥 Services created: {total_services}")
        print(f"📋 Cases created: {total_cases}")
        print(f"🤖 Cases processed by AI: {processed_count}")
        print("\n🚀 You can now:")
        print("1. Run the FastAPI server: uvicorn fastapi_main:app --reload")
        print("2. Open Citizen Portal: http://localhost:8000/citizen.html")
        print("3. Open Frontline Dashboard: http://localhost:8000/dashboard.html")
        print("4. Access API docs: http://localhost:8000/docs")
        
        # Create HTML files info
        html_files_info = """
        
📁 HTML Files to create:
- Save citizen_ui as: static/citizen.html
- Save frontline_worker_ui as: static/dashboard.html
        
🔧 Next steps:
1. Install requirements: pip install -r requirements.txt
2. Run setup: python demo_data_setup.py
3. Start server: uvicorn fastapi_main:app --reload
        """
        print(html_files_info)
        
    except Exception as e:
        print(f"❌ Error creating demo data: {str(e)}")
        db.rollback()
    finally:
        db.close()

async def test_agent_workflow():
    """Test the complete agent workflow with a sample case"""
    print("\n🧪 Testing Agent Workflow...")
    
    db = SessionLocal()
    try:
        # Get a random unprocessed case
        case = db.query(Case).filter(Case.status == CaseStatus.SUBMITTED).first()
        
        if case:
            print(f"Testing with Case #{case.id}: {case.title}")
            
            agent_system = FrontlineAgentSystem(db)
            result = await agent_system.process_case(case.id)
            
            print("Workflow Result:")
            print(json.dumps(result, indent=2, default=str))
        else:
            print("No unprocessed cases found for testing")
            
    except Exception as e:
        print(f"Error in workflow test: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Starting Frontline Worker Support AI Demo Setup")
    print("=" * 60)
    
    # Create tables first
    create_tables()
    print("📊 Database tables created")
    
    # Run the demo data creation
    asyncio.run(create_demo_data())
    
    # Test the agent workflow
    asyncio.run(test_agent_workflow())