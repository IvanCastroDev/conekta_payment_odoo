
from odoo import api, models


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['conekta'] = {'mode': 'unique', 'domain': [('type', '=', 'bank')]}
        res['conekta_oxxo'] = {'mode': 'unique', 'domain': [('type', '=', 'bank')]}
        res['conekta_spei'] = {'mode': 'unique', 'domain': [('type', '=', 'bank')]}
        return res
