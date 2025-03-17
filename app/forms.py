# app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional

class BaseFilterForm(FlaskForm):
    """Formulario base para filtros comunes en diferentes secciones"""
    fecha_inicio = DateField('Fecha inicio', validators=[Optional()], format='%Y-%m-%d')
    fecha_fin = DateField('Fecha fin', validators=[Optional()], format='%Y-%m-%d')
    submit = SubmitField('Filtrar')

class ReporteForm(FlaskForm):
    """Formulario para generar reportes"""
    periodo = SelectField('Período', choices=[
        ('dia', 'Día actual'),
        ('semana', 'Semana actual'),
        ('mes', 'Mes actual'),
        ('personalizado', 'Personalizado')
    ], validators=[DataRequired()])
    
    fecha_inicio = DateField('Fecha inicio', validators=[Optional()], format='%Y-%m-%d')
    fecha_fin = DateField('Fecha fin', validators=[Optional()], format='%Y-%m-%d')
    
    formato = SelectField('Formato', choices=[
        ('csv', 'CSV'),
        ('excel', 'Excel')
    ], default='csv', validators=[DataRequired()])
    
    nombre = StringField('Nombre del reporte', validators=[Optional()])
    
    submit = SubmitField('Generar Reporte') 
