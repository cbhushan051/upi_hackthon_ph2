"""
Docker manager module for restarting services after code changes.
"""

import logging
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)


class DockerManager:
    """Handles Docker container lifecycle management."""
    
    def __init__(self, compose_file: str = "docker-compose.yml"):
        """
        Initialize Docker manager.
        
        Args:
            compose_file: Path to docker-compose.yml file
        """
        self.compose_file = compose_file
    
    def restart_service(self, service_name: str) -> bool:
        """
        Restart a specific Docker service with robust error handling.
        """
        try:
            logger.info(f"Attempting to restart Docker service: {service_name}")
            
            # Check if docker-compose exists
            import shutil
            if not shutil.which("docker-compose"):
                error_msg = (
                    "Error: 'docker-compose' not found in the current environment. "
                    "If running inside a container, you may need to mount the Docker socket "
                    "and install the Docker CLI, or rely on a host-side file watcher."
                )
                print(f">>> [DockerManager] {error_msg}")
                logger.error(error_msg)
                return False

            # Stop the service
            subprocess.run(
                ["docker-compose", "-f", self.compose_file, "stop", service_name],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Start the service
            subprocess.run(
                ["docker-compose", "-f", self.compose_file, "up", "-d", service_name],
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info(f"Successfully restarted {service_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            msg = f"Failed to restart {service_name}: {e.stderr}"
            print(f">>> [DockerManager] {msg}")
            logger.error(msg)
            return False
        except Exception as e:
            msg = f"Error restarting {service_name}: {e}"
            print(f">>> [DockerManager] {msg}")
            logger.error(msg)
            return False
    
    def restart_all_services(self) -> bool:
        """
        Restart all Docker services with robust error handling.
        """
        try:
            logger.info("Attempting to restart all Docker services...")
            
            import shutil
            if not shutil.which("docker-compose"):
                error_msg = "Error: 'docker-compose' not found. Cannot restart services from this environment."
                print(f">>> [DockerManager] {error_msg}")
                logger.error(error_msg)
                return False

            # Stop all services
            subprocess.run(
                ["docker-compose", "-f", self.compose_file, "down"],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Start all services
            subprocess.run(
                ["docker-compose", "-f", self.compose_file, "up", "-d"],
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info("Successfully restarted all services")
            return True
            
        except subprocess.CalledProcessError as e:
            msg = f"Failed to restart services: {e.stderr}"
            print(f">>> [DockerManager] {msg}")
            logger.error(msg)
            return False
        except Exception as e:
            msg = f"Error restarting services: {e}"
            print(f">>> [DockerManager] {msg}")
            logger.error(msg)
            return False
    
    def get_service_for_file(self, file_path: str) -> Optional[str]:
        """
        Determine which Docker service should be restarted based on file path.
        
        Args:
            file_path: Path to the modified file
            
        Returns:
            Service name or None
        """
        # Map file paths to service names
        service_map = {
            "bene_bank/": "bene_bank",
            "rem_bank/": "rem_bank",
            "npci/": "npci",
            "payee_psp/": "payee_psp",
            "payer_psp/": "payer_psp",
        }
        
        for path_prefix, service_name in service_map.items():
            if file_path.startswith(path_prefix):
                return service_name
        
        return None
