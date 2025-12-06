import uuid
from sqlalchemy.orm import Session
from app.models.entities import Entity, EntityType
from app.models.entity_sources import EntitySource
from app.models.entity_profiles import EntityProfile
from datetime import datetime
from app.models.finder_session_results import FinderSessionResult

def process_and_save_apollo_results(db: Session, results: list, entity_type_hint: str = None, session_id: uuid.UUID = None):
    """
    Process Apollo results and save them to Entity, EntitySource, and EntityProfile tables.
    Also links them to the FinderSession if session_id is provided.
    """
    saved_entities = []

    for result in results:
        # Determine entity type
        # Apollo people results usually have 'first_name', 'last_name', 'person_id' or 'id'
        # Apollo company results usually have 'name', 'organization_id' or 'id'
        
        is_person = 'first_name' in result or 'last_name' in result or 'person_id' in result or 'email' in result
        
        # Override if hint provided
        if entity_type_hint:
            if entity_type_hint.lower() in ['person', 'people', 'talent']:
                is_person = True
            elif entity_type_hint.lower() in ['company', 'organization', 'business']:
                is_person = False
        
        provider_id = result.get('id') or result.get('person_id') or result.get('organization_id')
        if not provider_id:
            continue # Skip if no ID found
            
        # Check if source already exists
        existing_source = db.query(EntitySource).filter_by(
            provider='apollo',
            provider_entity_id=str(provider_id)
        ).first()

        entity_to_link = None

        if existing_source:
            # Update existing? For now, let's just skip or update raw_data
            existing_source.raw_data = result
            existing_source.entity.updated_at = datetime.utcnow()
            entity_to_link = existing_source.entity
        else:
            # Create new Entity
            new_entity = Entity(
                id=uuid.uuid4(),
                entity_type=EntityType.PERSON if is_person else EntityType.COMPANY,
                name=result.get('name') or f"{result.get('first_name', '')} {result.get('last_name', '')}".strip() or "Unknown",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_entity)
            db.flush() # Get ID

            # Create EntitySource
            new_source = EntitySource(
                id=uuid.uuid4(),
                entity_id=new_entity.id,
                provider='apollo',
                provider_entity_id=str(provider_id),
                raw_data=result,
                confidence_score=1.0
            )
            db.add(new_source)

            # Create EntityProfile
            # Map fields based on type
            profile_data = {}
            if is_person:
                profile_data = {
                    'name': new_entity.name,
                    'title': result.get('title') or result.get('headline'),
                    'email': result.get('email'),
                    'linkedin_url': result.get('linkedin_url'),
                    'location': result.get('city') or result.get('country'),
                    'company_name': result.get('organization_name') or result.get('organization', {}).get('name'),
                }
            else:
                profile_data = {
                    'name': new_entity.name,
                    'company_domain': result.get('domain') or result.get('primary_domain'),
                    'industry': result.get('industry') or (result.get('industries') or [None])[0],
                    'location': result.get('location') or result.get('address', {}).get('city'),
                    'employee_count': result.get('estimated_num_employees'),
                    'website_url': result.get('website_url'),
                    'linkedin_url': result.get('linkedin_url'),
                    'twitter_url': result.get('twitter_url'),
                    'facebook_url': result.get('facebook_url'),
                    'description': result.get('short_description')
                }

            new_profile = EntityProfile(
                id=uuid.uuid4(),
                entity_id=new_entity.id,
                name=profile_data.get('name'),
                title=profile_data.get('title'),
                email=profile_data.get('email'),
                company_name=profile_data.get('company_name'),
                company_domain=profile_data.get('company_domain'),
                location=profile_data.get('location'),
                industry=profile_data.get('industry'),
                employee_count=profile_data.get('employee_count'),
                linkedin_url=profile_data.get('linkedin_url'),
                website_url=profile_data.get('website_url'),
                data=result # Store full result in data as well for flexibility
            )
            db.add(new_profile)
            entity_to_link = new_entity
        
        saved_entities.append(entity_to_link)

        # Link to FinderSession if session_id provided
        if session_id and entity_to_link:
            # Check if already linked to avoid duplicates
            existing_link = db.query(FinderSessionResult).filter_by(
                session_id=session_id,
                entity_id=entity_to_link.id
            ).first()
            
            if not existing_link:
                new_link = FinderSessionResult(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    entity_id=entity_to_link.id,
                    created_at=datetime.utcnow()
                )
                db.add(new_link)
    
    db.commit()
    return saved_entities
