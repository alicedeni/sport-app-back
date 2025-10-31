from typing import Dict, Any, Optional
from sqlalchemy import or_
from datetime import datetime


def paginate_query(query, page=1, limit=20):
    """Применяет пагинацию к запросу"""
    page = max(1, int(page))
    limit = min(100, max(1, int(limit))) 
    offset = (page - 1) * limit
    
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    
    return {
        'items': items,
        'total': total,
        'page': page,
        'limit': limit,
        'pages': (total + limit - 1) // limit if limit > 0 else 0
    }


def build_filter_query(base_query, filters: Dict[str, Any], model):
    """Строит фильтры для запроса на основе словаря"""
    from sqlalchemy import and_, or_
    
    conditions = []
    
    for key, value in filters.items():
        if value is None or value == '':
            continue
        
        if key.endswith('_from'):
            attr_name = key[:-5]
            if hasattr(model, attr_name):
                conditions.append(getattr(model, attr_name) >= value)
        elif key.endswith('_to'):
            attr_name = key[:-3]
            if hasattr(model, attr_name):
                conditions.append(getattr(model, attr_name) <= value)
        elif key.endswith('_like') or key == 'query':
            attr_name = key.replace('_like', '')
            if key == 'query':
                if hasattr(model, 'name') and hasattr(model, 'email'):
                    conditions.append(
                        or_(
                            model.name.ilike(f'%{value}%'),
                            model.email.ilike(f'%{value}%')
                        )
                    )
                elif hasattr(model, 'name'):
                    conditions.append(model.name.ilike(f'%{value}%'))
                elif hasattr(model, 'email'):
                    conditions.append(model.email.ilike(f'%{value}%'))
            elif hasattr(model, attr_name):
                conditions.append(getattr(model, attr_name).ilike(f'%{value}%'))
        else:
            if hasattr(model, key):
                conditions.append(getattr(model, key) == value)
    
    if conditions:
        return base_query.filter(and_(*conditions))
    return base_query


def format_response(data, status=200, error=None):
    """Форматирует стандартный ответ API"""
    response = {'status': status}
    if error:
        response['error'] = error
    else:
        response['data'] = data
    return response


def parse_date_param(date_str: Optional[str]) -> Optional[datetime]:
    """Парсит дату из строки"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None

