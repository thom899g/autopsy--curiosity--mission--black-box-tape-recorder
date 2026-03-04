"""
Configuration module for Black Box Tape Recorder
Handles Firebase initialization and environment configuration
"""
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import firestore as google_firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class FirebaseConfig:
    """Firebase configuration container"""
    project_id: str
    credentials_path: Optional[str] = None
    service_account_info: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_env(cls) -> 'FirebaseConfig':
        """Initialize from environment variables"""
        project_id = os.getenv('FIREBASE_PROJECT_ID')
        if not project_id:
            raise ValueError("FIREBASE_PROJECT_ID must be set in environment")
        
        # Check for service account JSON file
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        # Check for service account JSON string
        service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
        service_account_info = None
        
        if service_account_json:
            import json
            try:
                service_account_info = json.loads(service_account_json)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in FIREBASE_SERVICE_ACCOUNT_JSON")
        
        return cls(
            project_id=project_id,
            credentials_path=creds_path,
            service_account_info=service_account_info
        )


class BlackBoxConfig:
    """Main configuration manager"""
    
    def __init__(self):
        self.firebase_config = FirebaseConfig.from_env()
        self.app: Optional[firebase_admin.App] = None
        self.db: Optional[google_firestore.Client] = None
        self._initialized = False
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging system"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('blackbox.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def initialize_firebase(self) -> None:
        """Initialize Firebase connection with proper error handling"""
        if self._initialized:
            self.logger.warning("Firebase already initialized")
            return
        
        try:
            # Check if default app already exists
            if not firebase_admin._apps:
                # Try multiple credential sources
                if self.firebase_config.service_account_info:
                    cred = credentials.Certificate(
                        self.firebase_config.service_account_info
                    )
                elif self.firebase_config.credentials_path:
                    if not Path(self.firebase_config.credentials_path).exists():
                        raise FileNotFoundError(
                            f"Credentials file not found: {self.firebase_config.credentials_path}"
                        )
                    cred = credentials.Certificate(self.firebase_config.credentials_path)
                else:
                    # Try application default credentials
                    cred = credentials.ApplicationDefault()
                
                self.app = firebase_admin.initialize_app(
                    cred,
                    {
                        'projectId': self.firebase_config.project_id,
                    }
                )
                self.logger.info("Firebase app initialized successfully")
            else:
                self.app = firebase_admin.get_app()
                self.logger.info("Using existing Firebase app")
            
            # Initialize Firestore
            self.db = firestore.client()
            
            # Test connection
            test_doc = self.db.collection('_health_check').document('connection_test')
            test_doc.set({'tested_at': datetime.utcnow().isoformat()})
            test_doc.delete()
            
            self._initialized = True
            self.logger.info("Firestore connection validated")
            
        except Exception as e:
            self.logger