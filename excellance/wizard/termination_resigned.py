from odoo import fields,models

class TerminationResignation(models.TransientModel):
    _name = 'termination.resignation'

    filter_type = fields.Selection([('termination','Termination'),('resignation','Resignation')])
    reason = fields.Char()
    date = fields.Date()
    employee_id = fields.Many2one('hr.employee')

    def submit_data(self):
        print(self.employee_id)
        if self.filter_type == 'termination':
            self.employee_id.reason = self.reason
            self.employee_id.date = self.date
            self.employee_id.employee_state = 'termination'
            self.employee_id.employee_state_vis = True
            self.employee_id.state = 'terminated'
            contracts = self.env['hr.contract'].search([('employee_id','=',self.employee_id.id),('state','=','open')])
            # print(contracts)
            for line in contracts:
                line.state = 'cancel'
        if self.filter_type == 'resignation':
            self.employee_id.reason = self.reason
            self.employee_id.date = self.date
            self.employee_id.employee_state = 'resignation'
            self.employee_id.employee_state_vis = True
            self.employee_id.state = 'resigned'
            contracts = self.env['hr.contract'].search(
                [('employee_id', '=', self.employee_id.id), ('state', '=', 'open')])
            print(contracts)
            for line in contracts:
                line.state = 'cancel'
