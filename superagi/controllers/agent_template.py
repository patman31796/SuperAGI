from fastapi import APIRouter
from fastapi import HTTPException, Depends
from fastapi_sqlalchemy import db
from pydantic_sqlalchemy import sqlalchemy_to_pydantic

from main import get_config
from superagi.helper.auth import get_user_organisation
from superagi.models.agent import Agent
from superagi.models.agent_config import AgentConfiguration
from superagi.models.agent_template import AgentTemplate
from superagi.models.agent_template_config import AgentTemplateConfig
from superagi.models.agent_workflow import AgentWorkflow

router = APIRouter()


@router.post("/create", status_code=201, response_model=sqlalchemy_to_pydantic(AgentTemplate))
def create_agent_template(agent_template: sqlalchemy_to_pydantic(AgentTemplate, exclude=["id"]),
                          organisation=Depends(get_user_organisation)):
    """Creates an agent template"""

    agent_workflow = db.session.query(AgentWorkflow).get(agent_template.agent_workflow_id)

    if not agent_workflow:
        raise HTTPException(status_code=404, detail="Agent Workflow not found")
    db_agent_template = AgentTemplate(agent_workflow_id=agent_template.agent_workflow_id,
                                      name=agent_template.name,
                                      organisation_id=organisation.id,
                                      description=agent_template.description)
    db.session.add(db_agent_template)
    db.session.commit()

    return db_agent_template


@router.get("/get/{agent_template_id}")
def get_agent_template(template_source, agent_template_id: int, organisation=Depends(get_user_organisation)):
    """Get particular agent_template details. All major configs goals, constraints, evaluation are shown in the frontend."""
    if template_source == "local":
        db_agent_template = db.session.query(AgentTemplate).filter(AgentTemplate.organisation_id == organisation.id,
                                                                   AgentTemplate.id == agent_template_id).first()
        if not db_agent_template:
            raise HTTPException(status_code=404, detail="Agent execution not found")
        template = db_agent_template.to_dict()
        configs = {}
        agent_template_configs = db.session.query(AgentTemplateConfig).filter(
            AgentTemplateConfig.agent_template_id == agent_template_id).all()
        for agent_template_config in agent_template_configs:
            configs[agent_template_config.key] = {"value": agent_template_config.value}
        template["configs"] = configs
    else:
        template = AgentTemplate.fetch_marketplace_detail(agent_template_id)

    return template


@router.post("/update_details/{agent_template_id}", response_model=sqlalchemy_to_pydantic(AgentTemplate))
def update_agent_template(agent_template_id: int,
                          agent_configs: dict,
                          organisation=Depends(get_user_organisation)):
    """Update agent template"""
    db_agent_template = db.session.query(AgentTemplate).filter(AgentTemplate.organisation_id == organisation.id,
                                                               AgentTemplate.id == agent_template_id).first()
    if db_agent_template is None:
        raise HTTPException(status_code=404, detail="Agent Template not found")

    for key, value in agent_configs.items():
        agent_template_config = db.session.query(AgentTemplateConfig).filter(
            AgentTemplateConfig.agent_template_id == agent_template_id, AgentTemplateConfig.key == key).first()
        if agent_template_config is None:
            # create the template config
            agent_template_config = AgentTemplateConfig(agent_template_id=agent_template_id, key=key)
        agent_template_config.value = value["value"]
        db.session.add(agent_template_config)
    db.session.commit()

    return db_agent_template


@router.post("/save_agent_as_template/{agent_id}")
def save_agent_as_template(agent_id: str,
                           organisation=Depends(get_user_organisation)):
    """Save agent as template"""
    agent = db.session.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent_configurations = db.session.query(AgentConfiguration).filter_by(agent_id=agent_id).all()
    if not agent_configurations:
        raise HTTPException(status_code=404, detail="Agent configurations not found")
    agent_template = AgentTemplate(name=agent.name, description=agent.description,
                                   agent_workflow_id=agent.agent_workflow_id,
                                   organisation_id=organisation.id)
    db.session.add(agent_template)
    db.session.commit()
    main_keys = AgentTemplate.main_keys()
    for agent_configuration in agent_configurations:
        if agent_configuration.key not in main_keys:
            continue
        agent_template_config = AgentTemplateConfig(agent_template_id=agent_template.id, key=agent_configuration.key,
                                                    value=agent_configuration.value)
        db.session.add(agent_template_config)
    db.session.commit()
    db.session.flush()
    return agent_template.to_dict()


@router.get("/list")
def list_agent_templates(template_source="local", search_str="", page=0, organisation=Depends(get_user_organisation)):
    """List agent templates"""
    output_json = []
    if template_source == "local":
        templates = db.session.query(AgentTemplate).filter(AgentTemplate.organisation_id == organisation.id).all()
        for template in templates:
            output_json.append(template)
    else:
        local_templates = db.session.query(AgentTemplate).filter(AgentTemplate.organisation_id == organisation.id,
                                                                 AgentTemplate.marketplace_template_id != None).all()
        local_templates_hash = {}
        for local_template in local_templates:
            local_templates_hash[local_template.marketplace_template_id] = True
        templates = AgentTemplate.fetch_marketplace_list(search_str, page)

        for template in templates:
            template["is_installed"] = local_templates_hash.get(template["id"], False)
            template["organisation_id"] = organisation.id
            output_json.append(template)

    return output_json


@router.get("/marketplace/list")
def list_marketplace_templates(page=0):
    """Get all marketplace agent templates"""
    organisation_id = get_config("MARKETPLACE_ORGANISATION_ID")
    page_size = 30
    templates = db.session.query(AgentTemplate).filter(AgentTemplate.organisation_id == organisation_id).offset(
        page * page_size).limit(page_size).all()
    output_json = []
    for template in templates:
        output_json.append(template)
    return output_json


@router.get("/marketplace/template_details/{agent_template_id}")
def marketplace_template_detail(agent_template_id):
    """Get marketplace template details"""
    organisation_id = get_config("MARKETPLACE_ORGANISATION_ID")
    template = db.session.query(AgentTemplate).filter(AgentTemplate.organisation_id == organisation_id,
                                                      AgentTemplate.id == agent_template_id).first()

    template_configs = db.session.query(AgentTemplateConfig).filter(
        AgentTemplateConfig.agent_template_id == template.id).all()

    workflow = db.session.query(AgentWorkflow).filter(AgentWorkflow.id == template.agent_workflow_id).first()

    output_json = {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "agent_workflow_id": template.agent_workflow_id,
        "agent_workflow_name": workflow.name,
        "configs": {template_config.key: {"value": template_config.value} for template_config in template_configs}
    }
    return output_json


@router.post("/download", status_code=201)
def download_template(agent_template_id: int,
                             organisation=Depends(get_user_organisation)):
    """Create new agent with configurations

    Parameters:
        agent_template_id: agent template id
    """
    template = AgentTemplate.clone_agent_template_from_marketplace(db, organisation.id, agent_template_id)
    return template.to_dict()


@router.get("/agent_config", status_code=201)
def fetch_agent_config_from_template(agent_template_id: int,
                                     organisation=Depends(get_user_organisation)):
    """Fetch agent config from template

    Parameters:
     agent_template_id: agent template id
    """
    agent_template = db.session.query(AgentTemplate).filter(AgentTemplate.id == agent_template_id,
                                                            AgentTemplate.organisation_id == organisation.id).first()
    if not agent_template:
        raise HTTPException(status_code=404, detail="Template not found")

    template_config = db.session.query(AgentTemplateConfig).filter(
        AgentTemplateConfig.agent_template_id == agent_template_id).all()
    template_config_dict = {}
    main_keys = AgentTemplate.main_keys()
    for config in template_config:
        if config.key in main_keys:
            template_config_dict[config.key] = config.value

    template_config_dict["agent_template_id"] = agent_template.id
    return template_config_dict
