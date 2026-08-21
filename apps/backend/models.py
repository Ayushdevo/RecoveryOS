import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from apps.backend.database import Base

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(String, primary_key=True, index=True)
    tenure_days = Column(Integer)
    merchant_category = Column(String)
    preferred_payment_method = Column(String)
    historical_success_rate = Column(Float)
    historical_failure_rate = Column(Float)
    velocity_24h = Column(Integer)
    time_since_last_success_days = Column(Float)
    
    transactions = relationship("Transaction", back_populates="customer")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id"), index=True)
    amount = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    payment_method = Column(String)
    merchant_category = Column(String)
    status = Column(String)  # 'captured', 'failed', 'abandoned', 'processing', 'escalated'
    gateway_code = Column(String, nullable=True)
    failure_reason = Column(String, nullable=True)
    is_retry = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    original_transaction_id = Column(String, nullable=True)
    recovered = Column(Boolean, default=False)
    recovered_amount = Column(Float, default=0.0)
    recovery_intervention = Column(String, nullable=True)
    
    customer = relationship("Customer", back_populates="transactions")
    actions = relationship("RecoveryAction", back_populates="transaction")

class RecoveryAction(Base):
    __tablename__ = "recovery_actions"
    
    id = Column(String, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True)
    action_type = Column(String)  # 'retry', 'reminder', 'link', 'escalate', 'none'
    status = Column(String)  # 'scheduled', 'executing', 'success', 'failed', 'rejected_by_policy'
    idempotency_key = Column(String, unique=True, index=True)
    attempt_number = Column(Integer)
    scheduled_at = Column(DateTime, default=datetime.datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    model_probability = Column(Float, nullable=True)
    expected_value = Column(Float, nullable=True)
    
    transaction = relationship("Transaction", back_populates="actions")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    transaction_id = Column(String, nullable=True, index=True)
    customer_id = Column(String, nullable=True, index=True)
    action_type = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    input_context = Column(Text, nullable=True)  # JSON serialized
    prediction_probability = Column(Float, nullable=True)
    agent_reasoning = Column(Text, nullable=True)
    policy_decision = Column(String)  # 'approved', 'rejected'
    policy_reason = Column(Text, nullable=True)
    execution_result = Column(Text, nullable=True)
    recovered_amount = Column(Float, default=0.0)
    failure_reason = Column(Text, nullable=True)
