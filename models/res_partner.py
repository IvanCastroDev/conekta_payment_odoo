
import logging
from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    conekta_client_id = fields.Char('Conekta cliente ID', help='Identificador del cliente en conekta', readonly=True)
