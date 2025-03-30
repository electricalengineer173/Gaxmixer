import os
import asyncio
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String
from dotenv import load_dotenv
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, ForeignKey, Enum, Text, TIMESTAMP
)
import asyncpg
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from dynamictool.schemas import UnitType
# Load environment variables
load_dotenv()

# Get the database URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL is missing in the environment variables.")

# Ensure asyncpg is used for async operations
DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# ✅ Fix SSL connection issue for NeonDB
ssl_context = ssl.create_default_context()
connect_args = {"server_settings": {"sslmode": "require"}}

# ✅ Create an async engine with SSL
async_engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20, connect_args=connect_args)

# ✅ Create session factory
async_session = sessionmaker(
    bind=async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# ✅ Base class for models
Base = declarative_base()



class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String, default="user")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    email = Column(String, unique=True, index=True)
    #items = relationship("Item", back_populates="owner")
    projects = relationship("Project", back_populates="owner")  # Cascad



# ---------------- PROJECT ----------------

class Project(Base):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))

    owner = relationship("User", back_populates="projects")

    # Cascading delete for all related tables
    cases = relationship("Case", back_populates="project", single_parent=True, cascade="all, delete-orphan")
    gas_composition = relationship("GasComposition", back_populates="project", cascade="all, delete-orphan")
    inlet_conditions = relationship("InletCondition", back_populates="project", single_parent=True, cascade="all, delete-orphan")
    calculated_properties = relationship("CalculatedProperty", back_populates="project")
    selected_components = relationship("SelectedComponent", back_populates="project", cascade="all, delete")


# ---------------- CASES ----------------
class Case(Base):
    __tablename__ = "cases"

    case_id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    case_number = Column(Integer, nullable=False)  # Incremental case number per project

    project = relationship("Project", back_populates="cases")
    inlet_conditions = relationship("InletCondition", back_populates="case", cascade="all, delete-orphan")
    gas_compositions = relationship("GasComposition", back_populates="case", cascade="all, delete-orphan")
    calculated_properties = relationship("CalculatedProperty", back_populates="case")
    selected_components = relationship("SelectedComponent", back_populates="case", cascade="all, delete-orphan")


# # ---------------- GASES ----------------
class Gas(Base):
    __tablename__ = "gases"

    gas_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    molecular_weight = Column(Float, nullable=False)
    density = Column(Float, nullable=False)
    critical_pressure = Column(Float, nullable=False)
    critical_temperature = Column(Float, nullable=False)
    boiling_point = Column(Float, nullable=False)
   
    toxicity = Column(Boolean, default=False)
    explosive = Column(Boolean, default=False)
    flammable = Column(Boolean, default=False)
    corrosive = Column(Boolean, default=False)
    oxidizing = Column(Boolean, default=False)
    sour = Column(Boolean, default=False)

# # ---------------- INLET CONDITIONS ----------------
class InletCondition(Base):
    __tablename__ = "inlet_conditions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False)  # Already present
    description = Column(Text, nullable=True)
    
    # Define Other Columns
    ambient_pressure = Column(Float, nullable=True)
    ambient_pressure_unit = Column(Enum("Pa", "bar", "atm", name="ambient_pressure_units"), nullable=True)
    ambient_temperature = Column(Float, nullable=True)
    ambient_temperature_unit = Column(Enum("K", "C", "F", name="ambient_temperature_units"), nullable=True)

    guarantee_point = Column(Boolean, default=False)
    suppress = Column(Boolean, default=False)
    pressure = Column(Float, nullable=True)
    pressure_unit = Column(Enum("Pa", "bar", "atm", name="pressure_units"), nullable=False)
    temperature = Column(Float, nullable=True)
    temperature_unit = Column(Enum("K", "C", "F", name="temperature_units"), nullable=False)
    flow_type = Column(Enum("Mass flow", "Standard volumetric flow", "Volumetric flow", name="flow_types"), nullable=False)
    flow_value = Column(Float, nullable=True)
    flow_unit = Column(Enum("kg/s", "m³/s", "SLPM", name="flow_units"), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="inlet_conditions")
    case = relationship("Case", back_populates="inlet_conditions")


# # ---------------- CALCULATED PROPERTIES ----------------
class CalculatedProperty(Base):
    __tablename__ = "calculated_properties"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False)  # Added case_id
    molar_mass = Column(Float, nullable=False)
    volumetric_flow = Column(Float, nullable=False)
    standard_volumetric_flow = Column(Float, nullable=False)
    vapor_mole_fraction = Column(Float, nullable=False)
    relative_humidity = Column(Float, nullable=False)
    specific_heat_cp = Column(Float, nullable=False)
    specific_heat_cv = Column(Float, nullable=False)
    specific_heat_ratio = Column(Float, nullable=False)
    specific_gas_constant = Column(Float, nullable=False)
    specific_gravity = Column(Float, nullable=False)
    density = Column(Float, nullable=False)
    compressibility_factor = Column(Float, nullable=False)
    speed_of_sound = Column(Float, nullable=False)
    dew_point = Column(Float, nullable=False)

    project = relationship("Project", back_populates="calculated_properties")
    case = relationship("Case", back_populates="calculated_properties")  # Added relationship


# Selected Gas Table (Tracks User Selections)
class SelectedGas(Base):
    __tablename__ = "selected_gases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)  # Assuming user selection
    gas_name = Column(String, ForeignKey("gases.name"))
   
    gas = relationship("Gas")

#below table related to app.post("/user/component-select/", response_model=List[ComponentResponse]) 
class SelectedComponent(Base):
    __tablename__ = "selected_component"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False)  # ✅ Reference to `cases.case_id`
    gas_id = Column(Integer, ForeignKey("gases.gas_id", ondelete="CASCADE"), nullable=False)  # ✅ Changed from `gas_name` to `gas_id`
    sequence_number = Column(Integer, nullable=False)

    project = relationship("Project", back_populates="selected_components")
    case = relationship("Case", back_populates="selected_components")  
    gas = relationship("Gas")

# ---------------- GAS COMPOSITION TABLE ----------------
class GasComposition(Base):
    __tablename__ = "gas_composition"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False)  # ✅ Changed from `case_number` to `case_id`
    gas_id = Column(Integer, ForeignKey("gases.gas_id", ondelete="CASCADE"), nullable=False)
    sequence_number = Column(Integer, nullable=False)  # Order of gases in selection
    amount = Column(Float, nullable=True, default=None)  # Default NULL
    #unit = Column(String, nullable=False, default="mol %")  # Default "mol %"
    unit = Column(Enum(UnitType), nullable=False, default=UnitType.MOL_PERCENT)  # ✅ Used Enum
    project = relationship("Project", back_populates="gas_composition")
    case = relationship("Case", back_populates="gas_compositions")  
    gas = relationship("Gas")

# ✅ Force table creation on startup
async def create_tables():
    async with async_engine.begin() as conn:
        print("🔄 Creating tables in database...")
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables successfully created in Neon Database.")

# ✅ Startup function to initialize database
async def startup_event():
    await create_tables()

# ✅ Async dependency for database session
async def get_db():
    async with async_session() as session:
        yield session


# Relationship: This allows fetching all related items for a user
#The items relationship is not a column in the database.
#It enables automatic retrieval of all items linked to a user.

