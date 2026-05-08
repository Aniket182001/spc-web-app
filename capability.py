from flask import Blueprint

capability_bp = Blueprint('capability', __name__)

@capability_bp.route('/capability')
def capability_home():

    return """
    <h2>📊 Capability Module Coming Soon</h2>
    <p>Cp / Cpk calculations will be added here.</p>
    """