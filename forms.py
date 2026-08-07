from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, BooleanField, SelectField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length

class LoginForm(FlaskForm):
  email = StringField('Email', validators=[DataRequired()])
  password = PasswordField('Password', validators=[DataRequired()])
  submit = SubmitField('Sign In')

class PlayersForm(FlaskForm):
  name = StringField('Game Name', validators=[DataRequired()])
  starting_amount = IntegerField('Starting Amount', validators=[DataRequired()])
  email_2 = StringField('Player 2: Email')
  email_3 = StringField('Player 3: Email')
  email_4 = StringField('Player 4: Email')
  email_5 = StringField('Player 5: Email')
  email_6 = StringField('Player 6: Email')
  has_options = BooleanField('Has Options', default=True)
  has_fee = BooleanField('Has Transaction Fee', default=False)
  submit = SubmitField('Create Game')

class UpdatePlayersForm(FlaskForm):
  email_2 = StringField('New Player 1: Email')
  email_3 = StringField('New Player 2: Email')
  email_4 = StringField('New Player 3: Email')
  email_5 = StringField('New Player 4: Email')
  email_6 = StringField('New Player 5: Email')
  has_options = BooleanField('Has Options', default=True)
  has_fee = BooleanField('Has Transaction Fee', default=False)
  submit = SubmitField('Update Game')

class BuyStockForm(FlaskForm):
  ticker = StringField('Ticker: ', validators=[DataRequired()], render_kw={"placeholder": "Ticker"})
  quantity = IntegerField('Quantity: ', validators=[DataRequired()], render_kw={"placeholder": "Quantity"})
  submit = SubmitField('Buy')

class SellStockForm(FlaskForm):
  ticker = StringField('Ticker: ', validators=[DataRequired()], render_kw={"placeholder": "Ticker"})
  quantity = IntegerField('Quantity: ', validators=[DataRequired()], render_kw={"placeholder": "Quantity"})
  submit = SubmitField('Sell')

class ShortStockForm(FlaskForm):
  ticker = StringField('Ticker: ', validators=[DataRequired()], render_kw={"placeholder": "Ticker"})
  quantity = IntegerField('Quantity: ', validators=[DataRequired()], render_kw={"placeholder": "Quantity"})
  submit = SubmitField('Short')

class CoverStockForm(FlaskForm):
  ticker = StringField('Ticker: ', validators=[DataRequired()], render_kw={"placeholder": "Ticker"})
  quantity = IntegerField('Quantity: ', validators=[DataRequired()], render_kw={"placeholder": "Quantity"})
  submit = SubmitField('Cover')

class OptionsForm(FlaskForm):
  optionTicker = StringField('Ticker: ', validators=[DataRequired()], render_kw={"placeholder": "Ticker"})
  submit = SubmitField('Get Options')

class OptionChainForm(FlaskForm):
  optionTicker = StringField('Ticker: ', validators=[DataRequired()], render_kw={"placeholder": "Ticker"})
  expiry = SelectField('Expiration Date: ', validators=[DataRequired()], choices=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')])
  submit = SubmitField('Get Option Chain')

class CallStockForm(FlaskForm):
  optionTicker = StringField('Ticker: ', validators=[DataRequired()], render_kw={"placeholder": "Ticker"})
  expiry = StringField('Expiration Date: ', validators=[DataRequired()], render_kw={"placeholder": "Expiration Date"})
  contractSymbol = SelectField('Contract Symbol: ', validators=[DataRequired()], choices=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')])
  contracts = IntegerField('Contracts: ', validators=[DataRequired()], render_kw={"placeholder": "Contracts"})
  submit = SubmitField('Call')

class PutStockForm(FlaskForm):
  optionTicker = StringField('Ticker: ', validators=[DataRequired()], render_kw={"placeholder": "Ticker"})
  expiry = StringField('Expiration Date: ', validators=[DataRequired()], render_kw={"placeholder": "Expiration Date"})
  contractSymbol = SelectField('Contract Symbol: ', validators=[DataRequired()], choices=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')])
  contracts = IntegerField('Contracts: ', validators=[DataRequired()], render_kw={"placeholder": "Contracts"})
  submit = SubmitField('Put')

class ConfirmForm(FlaskForm):
  confirm = SubmitField('Confirm')

class RegisterForm(FlaskForm):
  email = StringField('Email', validators=[DataRequired()])
  password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
  submit = SubmitField('Register')

class ResetPasswordForm(FlaskForm):
  email = StringField('Email', validators=[DataRequired()])
  submit = SubmitField('Reset Password')

class TickerForm(FlaskForm):
  ticker = StringField('Ticker: ',
                      validators=[DataRequired()], render_kw={"placeholder": "Ticker"})
  submit = SubmitField('🔎')

