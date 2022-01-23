from odoo import fields,models,api,_
from datetime import datetime,date
import pytz
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError

UTC = pytz.utc
IST = pytz.timezone('Asia/Riyadh')

class ProjectTask(models.Model):
    _inherit = "project.task"

    state = fields.Selection([('pending','Pending'),('completed','Completed')],default='pending')



    def completed_project(self):
        self.state = 'completed'

        task_line = self.env['project.task'].search([('project_id', '=', self.project_id.id),('state','=','pending')])
        if len(task_line) == 0:
            self.project_id.state = 'completed'

class ProjectProject(models.Model):
    _inherit = "project.project"

    state = fields.Selection([('pending','Pending'),('completed','Completed')],default='pending')

    def completed_project(self):
        self.state = 'completed'

        task_line = self.env['project.task'].search([('project_id', '=', self.id)])
        for line in task_line:
            line.state = 'completed'

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    payslip_id = fields.Many2one('hr.payslip')
    overtime_amt = fields.Float()

    @api.onchange('unit_amount')
    def computeovertime(self):
        if self.unit_amount > 8.0:
            self.overtime_amt = self.unit_amount - 8.0
            self.overtime = True

        else:
            self.overtime = False
            self.overtime_amt = 0.0

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    timesheet_lines = fields.One2many('account.analytic.line','payslip_id')
    payable_amount = fields.Float()
    payment_count = fields.Integer(compute='compute_payment_count')

    def checkslipcreated(self):
        payslips = self.env['hr.payslip'].search([('date_from','=',self.date_from),('date_to','=',self.date_to),('employee_id','=',self.employee_id.id),('state','=','done')])
        if len(payslips) != 0:
            raise UserError('Payslip already created for this employee in this same period')

    def compute_payment_count(self):
        for line in self:
            line.payment_count = len(self.env['account.payment'].search([('payslip_id','=',line.id)]))

    def action_view_payment(self):
        contract_obj = self.env['account.payment'].search([('payslip_id','=',self.id)])
        contract_ids = []
        for each in contract_obj:
            contract_ids.append(each.id)
        view_id = self.env.ref('account.view_account_payment_form').id
        if contract_ids:
            if len(contract_ids) <= 1:
                value = {
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'account.payment',
                    'view_id': view_id,
                    'type': 'ir.actions.act_window',
                    'name': _('Payment Details'),
                    'res_id': contract_ids and contract_ids[0]
                }
            else:
                value = {
                    'domain': str([('id', 'in', contract_ids)]),
                    'view_type': 'form',
                    'view_mode': 'tree,form',
                    'res_model': 'account.payment',
                    'view_id': False,
                    'type': 'ir.actions.act_window',
                    'name': _('Payment Details'),
                    'res_id': contract_ids
                }

            return value

    def create_payment(self):
        return {
            'name': 'Salary Payment',
            'view_mode': 'form',
            'res_model': 'account.payment',
            'view_id': self.env.ref('account.view_account_payment_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                'default_payment_type': 'outbound',
                'default_partner_id': self.employee_id.address_home_id.id,
                'default_partner_type': 'supplier',
                'search_default_inbound_filter': 1,
                'default_purchase_order_id': self.id,
                'default_purchase_order_visibility': True,
                'default_move_journal_types': ('bank', 'cash'),
                'default_amount':self.payable_amount,
                'default_payslip_id':self.id,
                'default_payslip_visibility':True,
                'default_destination_account_id':self.env['account.account'].search([('name','=','Wages Payable'),('company_id','=',self.env.user.company_id.id)]).id,
                'default_ref':self.number,
            },

        }

    # def create_payment(self):
    #     return {
    #         'name': _('Payment'),
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_model': 'account.payment',
    #         'type': 'ir.actions.act_window',
    #         'context': {
    #             'default_project_id': self.id,
    #             'default_analytic_account_id': self.analytic_account_id.id,
    #         }
    #     }

    def compute_sheet(self):
        self.checkslipcreated()
        self.timesheet_payslip()
        res = super(HrPayslip, self).compute_sheet()
        return res

    def timesheet_payslip(self):
        timsheets = self.env['account.analytic.line'].search(
            [('employee_id', '=', self.employee_id.id), ('expenstatus', '=', 'unpaid'),
             ('date', '>=', self.date_from), ('date', '<=', self.date_to),
             ('project_id', '=', self.contract_id.project_id.id)])
        for line in timsheets:
            line.payslip_id = self.id

    def compute_overtime(self):
        amount = 0
        for line in self.move_id.line_ids:
            amount = amount + line.credit
        self.payable_amount = amount
        if self.employee_id.employee_type == 'internal':
            if self.employee_id.payment_type == 'monthly':
                timsheets = self.env['account.analytic.line'].search(
                    [('employee_id', '=', self.employee_id.id), ('expenstatus', '=', 'unpaid'),
                     ('date', '>=', self.date_from), ('date', '<=', self.date_to),
                     ('project_id', '=', self.contract_id.project_id.id),('overtime','=',True)])
                self.contract_id.overtime_amount = sum(timsheets.mapped('overtime_amt')) * self.contract_id.timesheet_cost

    def compute_overtime_done(self):
        res = super(HrPayslip, self).compute_overtime_done()
        amount = 0
        for line in self.move_id.line_ids:
            amount = amount + line.credit
        self.payable_amount = amount
        return res
        # if self.employee_id.employee_type == 'internal':
        #     if self.employee_id.payment_type == 'monthly':
        #         timsheets = self.env['account.analytic.line'].search(
        #             [('employee_id', '=', self.employee_id.id), ('expenstatus', '=', 'unpaid'),
        #              ('date', '>=', self.date_from), ('date', '<=', self.date_to),
        #              ('project_id', '=', self.contract_id.project_id.id), ('overtime', '=', True)])
        #         for line in timsheets:
        #             line.expenstatus = 'paid'


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payslip_id = fields.Many2one('hr.payslip')
    payslip_visibility = fields.Boolean()

class AssignEmployee(models.Model):
    _inherit = 'assign.employee'

    def update_contract(self):
        for line in self.employee_lines:
            if line.contract_created == False:
                structure_id = None
                if line.employee_id.payment_type == 'monthly':
                    structure_id = self.env['hr.payroll.structure'].search(
                        [('name', '=', 'Base for new structures')]).id
                if line.employee_id.payment_type == 'timesheet':
                    structure_id = self.env['hr.payroll.structure'].search(
                        [('name', '=', 'Timesheet Salary Structure')]).id
                contract = self.env['hr.contract'].create({
                    'project_id':self.project_id.id,
                    'name':'Contract For '+ line.employee_id.name + '('+self.project_id.name+')',
                    'employee_id':line.employee_id.id,
                    'department_id':line.employee_id.department_id.id,
                    'job_id':line.employee_id.job_id.id,
                    'date_start':line.start_date,
                    'date_end':line.end_date,
                    'employee_type':line.employee_id.employee_type,
                    'payment_type':line.employee_id.payment_type,
                    'wage':line.employee_id.wage,
                    'timesheet_cost':line.employee_id.timesheet_cost,
                    'struct_id':structure_id,
                    'resource_calendar_id':self.env['resource.calendar'].search([('name','=','Standard 40 hours/week')]).id,
                    'hr_responsible_id':line.employee_id.user_id.id,
                    'assign_id':self.id,
                    'journal_id': self.env['account.journal'].search([('name', '=', 'Miscellaneous Operations'), ('company_id', '=', self.env.user.company_id.id)]).id,
                })
                contract.state = 'open'
                line.employee_id.state = 'on job'
                self.state = 'contract created'
                line.contract_created = True


    def create_contract(self):
        for line in self.employee_lines:
            if line.contract_created == False:
                structure_id = None
                if line.employee_id.payment_type == 'monthly':
                    structure_id = self.env['hr.payroll.structure'].search([('name','=','Base for new structures')]).id
                if line.employee_id.payment_type == 'timesheet':
                    structure_id = self.env['hr.payroll.structure'].search([('name','=','Timesheet Salary Structure')]).id
                contract = self.env['hr.contract'].create({
                    'name':'Contract For '+ line.employee_id.name + '('+self.project_id.name+')',
                    'employee_id':line.employee_id.id,
                    'department_id':line.employee_id.department_id.id,
                    'job_id':line.employee_id.job_id.id,
                    'date_start':line.start_date,
                    'date_end':line.end_date,
                    'employee_type':line.employee_id.employee_type,
                    'payment_type':line.employee_id.payment_type,
                    'wage':line.employee_id.wage,
                    'timesheet_cost':line.employee_id.timesheet_cost,
                    'struct_id':structure_id,
                    'resource_calendar_id':self.env['resource.calendar'].search([('name','=','Standard 40 hours/week')]).id,
                    'hr_responsible_id':line.employee_id.user_id.id,
                    'assign_id': self.id,
                    'project_id':self.project_id.id,
                    'journal_id':self.env['account.journal'].search([('name','=','Miscellaneous Operations'),('company_id','=',self.env.user.company_id.id)]).id,
                })
                contract.state = 'open'
                line.employee_id.state = 'on job'
                self.state = 'contract created'
                line.contract_created = True


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    state = fields.Selection([('no job','No Job'),('on job','On Job'),('terminated','Terminated'),('resigned','Resigned')],default='no job')
    employee_state = fields.Selection([('termination', 'Termination'), ('resignation', 'Resignation')])
    reason = fields.Char()
    date = fields.Date()
    employee_id = fields.Many2one('hr.employee')
    employee_state_vis = fields.Boolean()


    def compute_job_state(self):
        employees = self.env['hr.employee'].search([])
        print(employees)
        for line in employees:
            current_date = datetime.now(IST).date()
            print(current_date)
            contracts = self.env['hr.contract'].search([('state','=','open'),('employee_id','=',line.id)])
            print(contracts)
            for con in contracts:
                if con.date_end < current_date:
                    con.state = 'close'
                    line.state = 'no job'

class ProjectEmployees(models.Model):
    _inherit = 'project.employees.main'

    @api.onchange('task_ref', 'task_id')
    def _domain_employeess(self):
        return {'domain': {'employee_id': [('job_id', '=', self.task_id.work_id.job_id.id),('state','=','no job')]}}

