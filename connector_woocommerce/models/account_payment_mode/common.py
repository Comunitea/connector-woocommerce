# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.component.core import Component
from odoo import fields, models


class AccountPaymentMode(models.Model):
    _inherit = "account.payment.mode"

    woo_code = fields.Char("Woocommerce code")


class PaymentModeBinder(Component):
    _name = "woo.account.payment.mode.binder"
    _inherit = "woocommerce.binder"
    _apply_on = "account.payment.mode"

    _model_name = "account.payment.mode"
    _external_field = "woo_code"

    def to_internal(self, external_id, unwrap=False, company=None):
        if company is None:
            company = self.env.user.company_id
        bindings = self.model.with_context(active_test=False).search(
            [(self._external_field, "=", external_id), ("company_id", "=", company.id)]
        )
        if not bindings:
            return self.model.browse()
        bindings.ensure_one()
        return bindings
