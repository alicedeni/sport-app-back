import os
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PointsServiceClient:
    """Клиент для сервиса расчета баллов"""
    
    def __init__(self, service_url: Optional[str] = None):
        self.service_url = service_url or os.environ.get('POINTS_SERVICE_URL')
        self.use_http = self.service_url is not None
        
        if not self.use_http:
            from app.infra.services.points_calculation_service import get_points_service
            self.local_service = get_points_service()
            logger.info("Using local points calculation service")
        else:
            logger.info(f"Using remote points service: {self.service_url}")
    
    def calculate_activity_metrics(
        self,
        activity_tag: str,
        activity_input_data: Dict,
        user_id: int
    ) -> Dict:
        """
        Рассчитать метрики активности
        
        Args:
            activity_tag: тег активности
            activity_input_data: данные активности
            user_id: ID пользователя
        
        Returns:
            Dict с метриками
        """
        if self.use_http:
            return self._calculate_via_http(activity_tag, activity_input_data, user_id)
        else:
            return self.local_service.calculate_activity_metrics(
                activity_tag,
                activity_input_data,
                user_id
            )
    
    def _calculate_via_http(
        self,
        activity_tag: str,
        activity_input_data: Dict,
        user_id: int
    ) -> Dict:
        """Вызов микросервиса через HTTP"""
        try:
            try:
                import requests
            except ImportError:
                raise RuntimeError(
                    "requests library is required for HTTP mode. "
                    "Install it with: pip install requests"
                )
            
            response = requests.post(
                f"{self.service_url}/calculate",
                json={
                    'activity_tag': activity_tag,
                    'activity_data': activity_input_data,
                    'user_id': user_id
                },
                timeout=5
            )
            response.raise_for_status()
            return response.json()['data']
        except Exception as e:
            logger.error(f"Error calling points service via HTTP: {e}")
            raise

_points_client = None

def get_points_client() -> PointsServiceClient:
    """Получить клиент сервиса расчета баллов"""
    global _points_client
    if _points_client is None:
        _points_client = PointsServiceClient()
    return _points_client

