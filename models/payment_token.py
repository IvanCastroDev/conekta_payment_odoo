
import logging
from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class PaymentToken(models.Model):
    _inherit = 'payment.token'

    conekta_token = fields.Char('Conekta token', help='payment token from Conekta')
