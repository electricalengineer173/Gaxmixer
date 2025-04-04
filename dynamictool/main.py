from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from dynamictool.schemas import UserCreate,GasCompositionUpdate,ComponentSelectRequest,ComponentResponse, ComponentSelectRequest,ProjectResponse1,GasRemoveRequest, SelectedGasResponse,GasSelectRequest, GasResponse, CaseResponse1, SelectedComponentCreateComposit,GasCompositionCreate, InletConditionCreate,GasNameResponse,GasResponse,GasCreate,SelectedComponentCreate, CaseCreate,CaseResponse,  ProjectCreate,ProjectResponse, UserResponse# Fix Import
from dynamictool.database import User,Gas,GasComposition,CalculatedProperty,User,Project,Case,InletCondition,SelectedComponent,SelectedGas#,SelectedComponentGasComposition
from dynamictool.database import get_db, startup_event
from sqlalchemy.future import select
from dynamictool.security import verify_password
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dynamictool.jwt_handler import create_access_token
from fastapi import HTTPException,status
from dynamictool.jwt_handler import get_current_user  # Import JWT validation function
from dynamictool.security import pwd_context
from fastapi.responses import JSONResponse
from fastapi import Request
from typing import List
from datetime import datetime, timezone
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import joinedload
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.inspection import inspect
from sqlalchemy import or_
from fastapi import Query
import pint
import math
import logging
from fastapi.middleware.cors import CORSMiddleware

# ✅ Use `lifespan` to ensure tables are created
@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_event()  # ✅ Ensure tables are created on startup
    yield  # Application runs
    print("✅ FastAPI shutdown complete.")

# ✅ Initialize FastAPI app with lifespan event
app = FastAPI(lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000","https://gas-dynamix.vercel.app"],
    #https://gas-dynamix.vercel.app/
    #allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


@app.get("/")
async def read_root():
    return {"message": "FastAPI is running!"}



@app.post("/login")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await db.execute(select(User).where(User.username == form_data.username))
    user = user.scalars().first()
    
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"id": user.id, "sub": user.username, "role": user.role})

    response = JSONResponse(content={"message": "Login successful"})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Prevents JavaScript access
        max_age=60 * 60 * 24,  # Expires in 1 day
        secure=True,  # Use only on HTTPS
        samesite="Strict",
    )

    return {"access_token": access_token, "token_type": "bearer", "role": user.role,"response":response}


@app.get("/admin/users", response_model=List[UserResponse])
async def get_all_users(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    # ✅ Only allow admin to access user list
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view users")

    result = await db.execute(select(User))
    users = result.scalars().all()
    return users


@app.post("/admin/create-users", status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # Require authentication
):
    # 🔹 Ensure only admins can create users
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create users"
        )

    # 🔹 Check if the user already exists (Use Async Execution)
    result = await db.execute(select(User).where(User.username == user.username))
    existing_user = result.scalar_one_or_none()  # ✅ Async-friendly equivalent of `.first()`

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # 🔹 Hash the password before storing it
    hashed_password = pwd_context.hash(user.password)

    # 🔹 Create a new user
    new_user = User(
        username=user.username,
        email=user.email,
        password=hashed_password,
        role=user.role,
        created_at= datetime.now(timezone.utc)
    )
    
    db.add(new_user)  # No need to `await` add()
    await db.commit()  # Use await
    await db.refresh(new_user)  # Use await

    return {"message": "User created successfully", "username": new_user.username, "role": new_user.role,"time":new_user.created_at}

@app.delete("/admin/users/{user_id}", response_model=dict)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    # ✅ Only admin can delete users
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete users")

    # Use await with async queries
    result = await db.execute(select(User).filter(User.id == user_id))
    db_user = result.scalar_one_or_none()
    print("db user",db_user)

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(db_user)
    await db.commit()
    return {"message": f"User '{user_id}' has been deleted"}


@app.get("/projects/", response_model=list[ProjectResponse])
async def get_projects(
    db: AsyncSession = Depends(get_db), 
    user: dict = Depends(get_current_user)  
):
    # ✅ Fetch projects owned by the logged-in user
    #result = await db.execute(select(Project).where(Project.user_id == user["id"]))
    print(user["id"])
    if user["role"] == "admin":  
        result = await db.execute(select(Project))  # Fetch all projects
    else:
        result = await db.execute(select(Project).where(Project.user_id == user["id"]))  # Fetch only user projects
    
    projects = result.scalars().all()
    return projects

@app.get("/users", response_model=List[UserResponse])
async def get_all_users(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):

    if user["role"] == "admin":  
        result = await db.execute(select(User))  # Fetch all projects
    else:
        result = await db.execute(select(User).where(User.id == user["id"]))  # Fetch only user projects
    
    users = result.scalars().all()
    return users
    
# @app.delete("/admin/projects/{project_id}/", status_code=204)
# async def delete_project(
#     project_id: int,
#     db: AsyncSession = Depends(get_db),
#     user: dict = Depends(get_current_user),  # Get the current user
# ):
#     # Check if the current user is an admin
#     if user["role"] != "admin":
#         raise HTTPException(status_code=403, detail="Only admins can delete projects")
    
#     # ✅ Retrieve the project to delete
#     result = await db.execute(select(Project).where(Project.project_id == project_id))
#     #project = result.scalars().first()
#     project_id = result.scalar_one_or_none()
#     if not project:
#         raise HTTPException(status_code=404, detail="Project not found")

#     # Get the project_id for deletion purposes
#     #project_id = project.project_id

#     # ✅ Delete associated data from related tables explicitly (optional, cascades should handle this)
    

#     # Example: Delete selected component gas composition
#     await db.execute(
#         delete(GasComposition).where(GasComposition.project_id == project_id)
#     )

#     # Example: Delete inlet conditions
#     await db.execute(
#         delete(InletCondition).where(InletCondition.project_id == project_id)
#     )

#     # Finally, delete the project itself
#     await db.delete(project)
#     await db.commit()

#     return {"detail": "Project and its associated data deleted successfully"}


@app.delete("/admin/projects/{project_id}/", status_code=202)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),  # Get the current user
):
    # Check if the current user is an admin
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete projects")
    
    # ✅ Retrieve the project to delete
    result = await db.execute(select(Project).where(Project.project_id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # ✅ Delete associated data from related tables explicitly (optional, cascades should handle this)
    

    # Example: Delete selected component gas composition
    await db.execute(
        delete(GasComposition).where(GasComposition.project_id == project_id)
    )

    # Example: Delete inlet conditions
    await db.execute(
        delete(InletCondition).where(InletCondition.project_id == project_id)
    )

    # Finally, delete the project itself
    await db.delete(project)
    await db.commit()

    return {"detail": "Project and its associated data deleted successfully"}


# 🚀 Admin Adds a New Gas (🔒 Protected Route)
@app.post("/admin/single-gase/", response_model=GasResponse)
async def add_gas(
    gas: GasCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)  # Only admins can add gases
):
    
        # ✅ Ensure only admins can create items
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create items"
        )
    new_gas =  Gas(
        name=gas.name,
        molecular_weight=gas.molecular_weight,
        density=gas.density,
        critical_pressure=gas.critical_pressure,
        critical_temperature=gas.critical_temperature,
        boiling_point=gas.boiling_point,
        toxicity=gas.toxicity,
        explosive=gas.explosive,
        flammable=gas.flammable,
        corrosive=gas.corrosive,
        oxidizing=gas.oxidizing,
        sour=gas.sour,
        #created_at= datetime.now(timezone.utc)
        
    )
    db.add(new_gas)
    await db.commit()
    await db.refresh(new_gas)
    
    return new_gas


# ✅ Upload CSV and insert data
@app.post("/admin/upload-gases-csv/")
async def upload_gases(file: UploadFile = File(...), db: AsyncSession = Depends(get_db),user: dict = Depends(get_current_user)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are allowed")
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to add gases")
    # ✅ Read CSV file
    df = pd.read_csv(file.file)

    # ✅ Ensure required columns exist
    expected_columns = {
        "name", "critical_temperature", "critical_pressure", "boiling_point", "density",
        "molecular_weight", "toxicity", "explosive", "flammable", "corrosive", "oxidizing"
    }
    if not expected_columns.issubset(df.columns):
        raise HTTPException(status_code=400, detail=f"Missing columns: {expected_columns - set(df.columns)}")

    # ✅ Convert boolean columns
    boolean_columns = ["toxicity","explosive", "flammable", "corrosive", "oxidizing"]
    for col in boolean_columns:
        df[col] = df[col].astype(bool)

    # ✅ Insert into database
    gases = [
        Gas(
            name=row["name"],
            critical_temperature=row["critical_temperature"],
            critical_pressure=row["critical_pressure"],
            boiling_point=row["boiling_point"],
            density=row["density"],
            molecular_weight=row["molecular_weight"],
            toxicity=row["toxicity"],
            explosive=row["explosive"],
            flammable=row["flammable"],
            corrosive=row["corrosive"],
            oxidizing=row["oxidizing"],
            sour=False  # Default value since it's missing in CSV
        )
        for _, row in df.iterrows()
    ]

    db.add_all(gases)
    await db.commit()

    return {"message": "Gases data uploaded successfully"}


@app.get("/user/projects/project_name/", response_model=list[ProjectResponse])
async def search_projects(
    name: str,  
    db: AsyncSession = Depends(get_db), 
    user: dict = Depends(get_current_user)  
):
    # ✅ Search for projects that match the name and belong to the logged-in user
    result = await db.execute(
        select(Project).where(Project.user_id == user["id"], Project.name.ilike(f"%{name}%"))
    )
    projects = result.scalars().all()

    if not projects:
        raise HTTPException(status_code=404, detail="No matching projects found")

    return projects


@app.post("/user/create-project/", response_model=ProjectCreate)
async def create_project(
    project: ProjectCreate,
    user: dict = Depends(get_current_user),  # Get logged-in user
    db: AsyncSession = Depends(get_db),

):
    new_project = Project(
        name=project.name, 
        description=project.description, 
        user_id=user["id"]  # Use logged-in user's ID
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)

    # Auto-create Case 1
    case_1 = Case(project_id=new_project.project_id, case_number=1)
    db.add(case_1)
    await db.commit()

    return new_project  # No gases yet!


@app.get("/gases/")
async def get_all_gases(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Gas).limit(limit))  
    gases = result.scalars().all()

    if not gases:
        raise HTTPException(status_code=404, detail="No gases found")

    return gases  # Pydantic will convert SQLAlchemy objects automatically


@app.post("/user/projects/{project_id}/select-gases/")
async def select_gases(
    project_id: int, 
    gas_ids: List[int],  # Expecting a list of gas IDs
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    # Fetch project
    project_result = await db.execute(select(Project).filter_by(project_id=project_id))
    project = project_result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find the first case (Case 1) for the given project
    case_result = await db.execute(select(Case).filter_by(project_id=project_id, case_number=1))
    case = case_result.scalars().first()

    if not case:
        raise HTTPException(status_code=404, detail="Case 1 not found")

    # Insert selected gases into SelectedComponent & initialize GasComposition
    for idx, gas_id in enumerate(gas_ids, start=1):
        selected_gas = SelectedComponent(
            project_id=project_id,
            case_id=case.case_id,
            gas_id=gas_id,
            sequence_number=idx
        )
        db.add(selected_gas)

        gas_composition = GasComposition(
            project_id=project_id,
            case_id=case.case_id,
            gas_id=gas_id,
            sequence_number=idx,
            amount=None,  # Default NULL
            unit="mol %"  # Default unit
        )
        db.add(gas_composition)

    # ✅ Ensure InletCondition is initialized if missing
    existing_inlet = await db.execute(
        select(InletCondition).filter_by(project_id=project_id, case_id=case.case_id)
    )
    existing_inlet = existing_inlet.scalars().first()

    if not existing_inlet:
        print("Initializing InletCondition as it was missing.")

        new_inlet_condition = InletCondition(
            project_id=project_id,
            case_id=case.case_id,
            description=None,
            ambient_pressure=None,
            ambient_pressure_unit="Pa",
            ambient_temperature=None,
            ambient_temperature_unit="K",
            guarantee_point=False,
            suppress=False,
            pressure=None,
            pressure_unit="Pa",
            temperature=None,
            temperature_unit="K",
            flow_type="Mass flow",
            flow_value=None,
            flow_unit="kg/s"
        )
        db.add(new_inlet_condition)

    await db.commit()
    return {"message": "Gases selected and initialized in gas composition for Case 1"}


@app.post("/user/projects/{project_id}/select-gases-correct/")
async def select_gases(
    project_id: int, 
    gas_ids: List[int],  # Expecting a list of gas IDs
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    # Fetch project and all cases associated with it
    project_result = await db.execute(select(Project).filter_by(project_id=project_id).options(selectinload(Project.cases)))
    project = project_result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.cases:
        raise HTTPException(status_code=404, detail="No cases found for this project")

    for case in project.cases:
        # Insert selected gases into SelectedComponent & initialize GasComposition
        for idx, gas_id in enumerate(gas_ids, start=1):
            selected_gas = SelectedComponent(
                project_id=project_id,
                case_id=case.case_id,
                gas_id=gas_id,
                sequence_number=idx
            )
            db.add(selected_gas)

            gas_composition = GasComposition(
                project_id=project_id,
                case_id=case.case_id,
                gas_id=gas_id,
                sequence_number=idx,
                amount=None,  # Default NULL
                unit="mol %"  # Default unit
            )
            db.add(gas_composition)

        # ✅ Ensure InletCondition is initialized if missing
        existing_inlet = await db.execute(
            select(InletCondition).filter_by(project_id=project_id, case_id=case.case_id)
        )
        existing_inlet = existing_inlet.scalars().first()

        if not existing_inlet:
            print(f"Initializing InletCondition for Case {case.case_number} as it was missing.")

            new_inlet_condition = InletCondition(
                project_id=project_id,
                case_id=case.case_id,
                description=None,
                ambient_pressure=None,
                ambient_pressure_unit="Pa",
                ambient_temperature=None,
                ambient_temperature_unit="K",
                guarantee_point=False,
                suppress=False,
                pressure=None,
                pressure_unit="Pa",
                temperature=None,
                temperature_unit="K",
                flow_type="Mass flow",
                flow_value=None,
                flow_unit="kg/s"
            )
            db.add(new_inlet_condition)

    await db.commit()
    return {"message": f"Gases selected and initialized in gas composition for all cases under Project {project_id}"}

@app.post("/projects/{project_id}/cases/")
async def create_case(project_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await db.rollback()  # Ensure a clean session

    # Get the latest case number
    last_case = await db.execute(
        select(Case).filter_by(project_id=project_id).order_by(Case.case_number.desc())
    )
    last_case = last_case.scalars().first()

    # Determine new case number
    new_case_number = 1 if not last_case else last_case.case_number + 1

    # Create new case
    new_case = Case(project_id=project_id, case_number=new_case_number)
    db.add(new_case)
    await db.flush()  # Ensure new_case gets an ID
    await db.refresh(new_case)

    print(f"New case created with ID: {new_case.case_id}")

    # Copy gases if last case exists
    if last_case:
        previous_gases = await db.execute(
            select(GasComposition).filter_by(project_id=project_id, case_id=last_case.case_id)
        )
        previous_gases = previous_gases.scalars().all()

        print(f"Found {len(previous_gases)} gases to copy.")

        for gas in previous_gases:
            new_gas_composition = GasComposition(
                project_id=project_id,
                case_id=new_case.case_id,  
                gas_id=gas.gas_id,
                sequence_number=gas.sequence_number,
                amount=None,
                unit="mol %"
            )
            db.add(new_gas_composition)

    # ✅ Initialize InletCondition with NULL values & default units
    new_inlet_condition = InletCondition(
        project_id=project_id,
        case_id=new_case.case_id,
        description=None,
        ambient_pressure=None,
        ambient_pressure_unit="Pa",
        ambient_temperature=None,
        ambient_temperature_unit="K",
        guarantee_point=False,
        suppress=False,
        pressure=None,
        pressure_unit="Pa",
        temperature=None,
        temperature_unit="K",
        flow_type="Mass flow",
        flow_value=None,
        flow_unit="kg/s"
    )
    db.add(new_inlet_condition)

    await db.commit()

    return {"message": f"Case {new_case_number} created and initialized"}





@app.put("/projects/{project_id}/cases/{case_id}/gases/{gas_id}/update/")
async def update_gas_composition(
    project_id: int,
    case_id: int,
    gas_id: int,
    update_data: GasCompositionUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    # Ensure the gas composition entry belongs to the specified project and case
    gas_entry = await db.execute(
        select(GasComposition)
        .filter_by(project_id=project_id, case_id=case_id, gas_id=gas_id)
    )
    gas_entry = gas_entry.scalars().first()

    if not gas_entry:
        raise HTTPException(status_code=404, detail="Gas composition not found for this project and case")

    # Update only the provided fields
    if update_data.amount is not None:
        gas_entry.amount = update_data.amount
    if update_data.unit is not None:
        gas_entry.unit = update_data.unit

    await db.commit()
    return {"message": "Gas composition updated successfully"}



@app.get("/projects/{project_id}/gas_compositions3")
async def get_gas_compositions(project_id: int, db: AsyncSession = Depends(get_db),user: dict = Depends(get_current_user)):
    try:
        # Asynchronous query to get Project, Case, and GasComposition details based on project_id
        stmt = select(Project).filter(Project.project_id == project_id).options(
            selectinload(Project.cases).selectinload(Case.gas_compositions)
        )

        # Execute the query asynchronously
        result = await db.execute(stmt)
        project_data = result.scalars().first()

        if not project_data:
            raise HTTPException(status_code=404, detail="No data found for the provided project ID")

        # Prepare the response in the required format
        project_response = {
            "project_id": project_data.project_id,
            "name": project_data.name,
            "description": project_data.description,
            "cases": []
        }

        # Collect cases and their respective gas compositions
        for case in project_data.cases:
            case_data = {
                "case_id": case.case_id,
                "case_number": case.case_number,
                "gas_compositions": []
            }

            # Collect all gas compositions for each case
            for gas_composition in case.gas_compositions:
                gas_composition_data = {
                    "gas_id": gas_composition.gas_id,
                    "gas_composition_id": gas_composition.id,
                    "sequence_number": gas_composition.sequence_number,
                    "amount": gas_composition.amount,
                    "unit": gas_composition.unit
                }
                case_data["gas_compositions"].append(gas_composition_data)

            project_response["cases"].append(case_data)

        return {"projects": [project_response]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")



@app.put("/projects/{project_id}/cases/{case_id}/inlet/{inlet_id}/update/")
async def update_inlet_condition(
    project_id: int,
    case_id: int,
    inlet_id: int,
    update_data: InletConditionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    try:
        # ✅ Fetch the inlet condition entry with proper query
        result = await db.execute(
            select(InletCondition)
            .filter(
                InletCondition.project_id == project_id,
                InletCondition.case_id == case_id,
                InletCondition.id == inlet_id
            )
            .options(selectinload(InletCondition.project), selectinload(InletCondition.case))  # ✅ Load relationships properly
        )
        inlet_entry = result.scalars().one_or_none()

        if not inlet_entry:
            raise HTTPException(status_code=404, detail="Inlet condition not found")

        # ✅ Apply updates dynamically for provided fields
        update_fields = update_data.dict(exclude_unset=True)
        for key, value in update_fields.items():
            setattr(inlet_entry, key, value)

        await db.commit()
        return {"message": "Inlet condition updated successfully"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.get("/projects/{project_id}/inlet_conditions")
async def get_inlet_conditions(project_id: int, db: AsyncSession = Depends(get_db),user: dict = Depends(get_current_user)):
    # Perform the query asynchronously
    stmt = (
        select(Project)
        .filter(Project.project_id == project_id)
        .options(
            selectinload(Project.cases)
            .selectinload(Case.inlet_conditions)  # Load inlet_conditions along with cases
        )
    )
    result = await db.execute(stmt)
    projects = result.scalars().all()

    response = []
    for project in projects:
        project_data = {
            "project_id": project.project_id,
            "name": project.name,
            "description": project.description,
            "cases": []
        }

        for case in project.cases:
            case_data = {
                "case_id": case.case_id,
                "case_number": case.case_number,
                "inlet_conditions": []
            }

            for inlet_condition in case.inlet_conditions:
                inlet_condition_data = {
                    "inlet_condition_id": inlet_condition.id,
                    "description": inlet_condition.description,
                    "ambient_pressure": inlet_condition.ambient_pressure,
                    "ambient_pressure_unit": inlet_condition.ambient_pressure_unit,
                    "ambient_temperature": inlet_condition.ambient_temperature,
                    "ambient_temperature_unit": inlet_condition.ambient_temperature_unit,
                    "guarantee_point": inlet_condition.guarantee_point,
                    "suppress": inlet_condition.suppress,
                    "pressure": inlet_condition.pressure,
                    "pressure_unit": inlet_condition.pressure_unit,
                    "temperature": inlet_condition.temperature,
                    "temperature_unit": inlet_condition.temperature_unit,
                    "flow_type": inlet_condition.flow_type,
                    "flow_value": inlet_condition.flow_value,
                    "flow_unit": inlet_condition.flow_unit
                }
                case_data["inlet_conditions"].append(inlet_condition_data)

            project_data["cases"].append(case_data)

        response.append(project_data)

    return {"projects": response}



#----------------------------------------------- Selected_Component-----------------------------------


#--------------------------------------------------------------Calculation----------------------------------------------------
# Initialize the Unit Registry
ureg = pint.UnitRegistry()

def convert_to_standard_units(inlet_condition):
    """Convert pressure, temperature, and flow values to standard SI units"""

    try:
        # Convert Pressure to Pa
        if inlet_condition.pressure_unit == "bar":
            pressure = (inlet_condition.pressure * ureg.bar).to(ureg.Pa).magnitude
        elif inlet_condition.pressure_unit == "atm":
            pressure = (inlet_condition.pressure * ureg.atm).to(ureg.Pa).magnitude
        elif inlet_condition.pressure is not None:
            pressure = inlet_condition.pressure  # Assume already in Pa
        else:
            raise ValueError("Pressure value is missing or invalid.")

        # Convert Temperature to Kelvin
        if inlet_condition.temperature_unit == "C":
            temperature = (inlet_condition.temperature * ureg.degC).to(ureg.K).magnitude
        elif inlet_condition.temperature_unit == "F":
            temperature = (inlet_condition.temperature * ureg.degF).to(ureg.K).magnitude
        elif inlet_condition.temperature is not None:
            temperature = inlet_condition.temperature  # Assume already in K
        else:
            raise ValueError("Temperature value is missing or invalid.")

        # Convert Flow Rate to m³/s
        if inlet_condition.flow_unit == "m³/s":
            flow_rate = inlet_condition.flow_value  # Already in m³/s
        elif inlet_condition.flow_unit == "SLPM":
            flow_rate = (inlet_condition.flow_value * ureg.liter / ureg.minute).to(ureg.meter**3 / ureg.second).magnitude
        elif inlet_condition.flow_unit == "kg/s":
            flow_rate = inlet_condition.flow_value  # Assume already in kg/s
        else:
            raise ValueError(f"Unsupported flow unit: {inlet_condition.flow_unit}")

        return pressure, temperature, flow_rate

    except Exception as e:
        raise ValueError(f"Error in unit conversion: {e}")


def calculate_molar_mass(gas_compositions):
    """Calculate molar mass from gas compositions with error handling."""
    try:
        molar_mass = sum(
            ((gas.amount / 100) * gas.gas.molecular_weight) if gas.amount is not None else 0
            for gas in gas_compositions
        )
        if molar_mass <= 0:
            raise ValueError("Calculated molar mass is zero or negative. Check gas compositions.")
        return molar_mass
    except Exception as e:
        raise ValueError(f"Error calculating molar mass: {e}")


def calculate_volumetric_flow(flow_rate, molar_mass, temperature, pressure):
    """Calculate volumetric flow using ideal gas law with error handling."""
    R = 8314  # J/kmol·K

    # Ensure values are valid before calculation
    if molar_mass <= 0:
        raise ValueError("Molar mass must be greater than zero.")
    if pressure <= 0:
        raise ValueError("Pressure must be greater than zero.")
    if temperature <= 0:
        raise ValueError("Temperature must be greater than zero.")

    return (flow_rate * R * temperature) / (pressure * molar_mass)

def calculate_additional_properties(volumetric_flow, molar_mass, temperature, pressure):
    """Calculate additional properties based on thermodynamic equations"""
    R = 8314  # J/kmol·K
    P_std = 101325  # Standard pressure in Pa
    T_std = 273.15  # Standard temperature in K
    gamma = 1.4  # Specific heat ratio for diatomic gases

    # Standard Volumetric Flow
    standard_volumetric_flow = (volumetric_flow * P_std * temperature) / (pressure * T_std)

    # Specific Gas Constant (J/kg·K)
    R_gas = R / molar_mass

    # Density (kg/m³)
    density = pressure / (R_gas * temperature)

    # Compressibility Factor (Z) (Ideal Gas)
    Z = 1.0  

    # Speed of Sound (m/s)
    speed_of_sound = (gamma * R_gas * temperature) ** 0.5

    return standard_volumetric_flow, R_gas, density, Z, speed_of_sound


def calculate_vapor_mole_fraction(gas_compositions):
    """Calculate vapor mole fraction from gas compositions"""
    vapor_mole_fraction = sum(
        (gas.amount / 100) if gas.gas.is_vapor else 0 for gas in gas_compositions
    )
    return vapor_mole_fraction

def calculate_relative_humidity(temperature, pressure, gas_compositions):
    """Calculate relative humidity using partial pressure of water vapor"""
    # Find partial pressure of H2O (if present in gas_compositions)
    p_h2o = sum(
        (gas.amount / 100) * pressure for gas in gas_compositions if gas.gas.name == "H2O"
    )

    # Antoine constants for water vapor (valid for 1-100°C)
    A, B, C = 8.07131, 1730.63, 233.426
    temp_C = temperature - 273.15  # Convert K to °C

    if temp_C < 0 or temp_C > 100:
        return None  # Antoine equation is not valid outside this range

    p_h2o_sat = 10**(A - (B / (temp_C + C))) * 133.322  # Convert mmHg to Pa
    relative_humidity = (p_h2o / p_h2o_sat) * 100 if p_h2o_sat else None
    return relative_humidity

def calculate_specific_heat_cp(gas_compositions):
    """Calculate specific heat at constant pressure (Cp) for a gas mixture"""
    return sum(
        (gas.amount / 100) * gas.gas.critical_pressure for gas in gas_compositions if gas.gas.critical_pressure
 is not None
    )

def calculate_specific_heat_cv(specific_heat_cp, specific_gas_constant):
    """Calculate specific heat at constant volume (Cv)"""
    return specific_heat_cp - specific_gas_constant

def calculate_specific_heat_ratio(specific_heat_cp, specific_heat_cv):
    """Calculate specific heat ratio (γ = Cp/Cv)"""
    return specific_heat_cp / specific_heat_cv if specific_heat_cv else None

def calculate_specific_gas_constant(molar_mass):
    """Calculate specific gas constant (R_specific)"""
    R_universal = 8314  # J/kmol·K
    return R_universal / molar_mass if molar_mass else None

def calculate_specific_gravity(density):
    """Calculate specific gravity (SG = ρ_gas / ρ_air)"""
    rho_air = 1.225  # kg/m³ at standard conditions
    return density / rho_air if density else None

def calculate_dew_point(temperature, relative_humidity):
    """Calculate dew point using Magnus-Tetens approximation"""
    if not relative_humidity:
        return None

    A, B = 17.62, 243.12  # Constants for Magnus equation
    alpha = math.log(relative_humidity / 100) + (A * (temperature - 273.15)) / (B + (temperature - 273.15))
    dew_point = (B * alpha) / (A - alpha) + 273.15  # Convert back to Kelvin
    return dew_point

@app.put("/projects/{project_id}/cases/{case_id}/calculate/")
async def calculate_properties(
    project_id: int,
    case_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Calculate molar mass and volumetric flow and update the database"""

    try:
        # Get Gas Composition
        gas_compositions_result = await db.execute(
            select(GasComposition)
            .options(joinedload(GasComposition.gas))
            .filter_by(project_id=project_id, case_id=case_id)
        )
        gas_compositions = gas_compositions_result.scalars().all()

        if not gas_compositions:
            raise HTTPException(status_code=404, detail="No gas compositions found")

        # Get Inlet Condition
        inlet_condition_result = await db.execute(
            select(InletCondition).filter_by(project_id=project_id, case_id=case_id)
        )
        inlet_condition = inlet_condition_result.scalars().first()

        if not inlet_condition:
            raise HTTPException(status_code=404, detail="No inlet conditions found")

        # Convert Units
        pressure, temperature, flow_rate = convert_to_standard_units(inlet_condition)

        # Check if any of the critical values is zero to prevent division errors
        if pressure == 0 or temperature == 0 or flow_rate == 0:
            raise HTTPException(status_code=400, detail="Critical values like pressure, temperature, or flow rate are zero")

        # Calculate Properties
        molar_mass = calculate_molar_mass(gas_compositions)
        volumetric_flow = calculate_volumetric_flow(flow_rate, molar_mass, temperature, pressure)
        standard_volumetric_flow, specific_gas_constant, density, compressibility_factor, speed_of_sound = \
            calculate_additional_properties(volumetric_flow, molar_mass, temperature, pressure)

        #vapor_mole_fraction = calculate_vapor_mole_fraction(gas_compositions)

        # Store Results in Database
        calculated_property = CalculatedProperty(
            project_id=project_id,
            case_id=case_id,
            molar_mass=molar_mass,
            volumetric_flow=volumetric_flow,
            standard_volumetric_flow=0.0,  # Placeholder
            vapor_mole_fraction=0.0,  # Ensure it's calculated
            relative_humidity=0.0,  # Placeholder or leave if not needed
            specific_heat_cp=0.0,  # Placeholder or leave if not needed
            specific_heat_cv=0.0,  # Placeholder or leave if not needed
            specific_heat_ratio=0.0,  # Placeholder or leave if not needed
            specific_gas_constant=specific_gas_constant,
            specific_gravity=0.0,  # Placeholder or leave if not needed
            density=0.0,  # Placeholder
            compressibility_factor=0.0,  # Placeholder
            speed_of_sound=0.0,  # Placeholder
            dew_point=0.0  # Placeholder or leave if not needed
        )

        db.add(calculated_property)
        await db.commit()

        return {
            "message": "Calculated properties updated",
            "molar_mass": f"{molar_mass:.3f} kg/kmol",
            "volumetric_flow": f"{volumetric_flow:.6f} m³/s",
            "standard_volumetric_flow": f"{standard_volumetric_flow:.6f} m³/s",
            "specific_gas_constant": f"{specific_gas_constant:.3f} J/kg·K",
            "density": f"{density:.3f} kg/m³",
            "compressibility_factor": f"{compressibility_factor:.3f}",
            "speed_of_sound": f"{speed_of_sound:.3f} m/s",
            #"vapor_mole_fraction": vapor_mole_fraction,  # Ensure it's returned
        }

    except ValueError as ve:
        logging.error(f"ValueError: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")



@app.get("/projects/{project_id}/calculated_properties")
async def get_calculated_properties(project_id: int, db: AsyncSession = Depends(get_db)):
    # Perform the query asynchronously
    stmt = (
        select(Project)
        .filter(Project.project_id == project_id)
        .options(
            selectinload(Project.cases)
            .selectinload(Case.calculated_properties)  # Load calculated_properties along with cases
        )
    )
    result = await db.execute(stmt)
    projects = result.scalars().all()

    response = []
    for project in projects:
        project_data = {
            "project_id": project.project_id,
            "name": project.name,
            "description": project.description,
            "cases": []
        }

        for case in project.cases:
            case_data = {
                "case_id": case.case_id,
                "case_number": case.case_number,
                "calculated_properties": []
            }

            for calculated_property in case.calculated_properties:
                calculated_property_data = {
                    "calculated_property_id": calculated_property.id,
                    "molar_mass": calculated_property.molar_mass,
                    "volumetric_flow": calculated_property.volumetric_flow,
                    "standard_volumetric_flow": calculated_property.standard_volumetric_flow,
                    "vapor_mole_fraction": calculated_property.vapor_mole_fraction,
                    "relative_humidity": calculated_property.relative_humidity,
                    "specific_heat_cp": calculated_property.specific_heat_cp,
                    "specific_heat_cv": calculated_property.specific_heat_cv,
                    "specific_heat_ratio": calculated_property.specific_heat_ratio,
                    "specific_gas_constant": calculated_property.specific_gas_constant,
                    "specific_gravity": calculated_property.specific_gravity,
                    "density": calculated_property.density,
                    "compressibility_factor": calculated_property.compressibility_factor,
                    "speed_of_sound": calculated_property.speed_of_sound,
                    "dew_point": calculated_property.dew_point
                }
                case_data["calculated_properties"].append(calculated_property_data)

            project_data["cases"].append(case_data)

        response.append(project_data)

    return {"projects": response}
