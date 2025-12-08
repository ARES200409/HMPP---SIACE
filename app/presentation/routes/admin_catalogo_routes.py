# RUTA: app/presentation/routes/admin_catalogo_routes.py
"""
Rutas para la gestión de catálogos (secciones y tipos de documento) 
por parte del AdministradorLegajos
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required, current_user
from app.decorators import role_required

admin_catalogo_bp = Blueprint('admin_catalogo', __name__, url_prefix='/legajo/catalogos')

# =====================================================================
# GESTIÓN DE SECCIONES
# =====================================================================

@admin_catalogo_bp.route('/secciones')
@login_required
@role_required('AdministradorLegajos')
def listar_secciones():
    """Lista todas las secciones de legajo."""
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        secciones = legajo_service._personal_repo.get_all_secciones()
        return render_template('admin/catalogos/listar_secciones.html', secciones=secciones)
    except Exception as e:
        current_app.logger.error(f"Error al listar secciones: {e}")
        flash('Error al cargar las secciones.', 'danger')
        return redirect(url_for('legajo.dashboard'))


@admin_catalogo_bp.route('/secciones/nueva', methods=['GET', 'POST'])
@login_required
@role_required('AdministradorLegajos')
def crear_seccion():
    """Crea una nueva sección de legajo."""
    if request.method == 'POST':
        nombre_seccion = request.form.get('nombre_seccion', '').strip()
        
        if not nombre_seccion:
            flash('El nombre de la sección es obligatorio.', 'danger')
            return render_template('admin/catalogos/crear_seccion.html')
        
        try:
            legajo_service = current_app.config['LEGAJO_SERVICE']
            audit_service = current_app.config['AUDIT_SERVICE']
            
            new_id = legajo_service._personal_repo.create_seccion(nombre_seccion)
            
            audit_service.log(
                current_user.id,
                'Catálogos',
                'CREAR_SECCION',
                f"Creó la sección '{nombre_seccion}' con ID {new_id}"
            )
            
            flash(f'Sección "{nombre_seccion}" creada exitosamente.', 'success')
            return redirect(url_for('admin_catalogo.listar_secciones'))
            
        except Exception as e:
            current_app.logger.error(f"Error al crear sección: {e}")
            flash(f'Error al crear la sección: {str(e)}', 'danger')
    
    return render_template('admin/catalogos/crear_seccion.html')


@admin_catalogo_bp.route('/secciones/editar/<int:id_seccion>', methods=['GET', 'POST'])
@login_required
@role_required('AdministradorLegajos')
def editar_seccion(id_seccion):
    """Edita una sección existente."""
    legajo_service = current_app.config['LEGAJO_SERVICE']
    
    try:
        seccion = legajo_service._personal_repo.get_seccion_by_id(id_seccion)
        if not seccion:
            flash('Sección no encontrada.', 'danger')
            return redirect(url_for('admin_catalogo.listar_secciones'))
        
        if request.method == 'POST':
            nombre_seccion = request.form.get('nombre_seccion', '').strip()
            
            if not nombre_seccion:
                flash('El nombre de la sección es obligatorio.', 'danger')
                return render_template('admin/catalogos/editar_seccion.html', seccion=seccion)
            
            try:
                audit_service = current_app.config['AUDIT_SERVICE']
                legajo_service._personal_repo.update_seccion(id_seccion, nombre_seccion)
                
                audit_service.log(
                    current_user.id,
                    'Catálogos',
                    'ACTUALIZAR_SECCION',
                    f"Actualizó la sección ID {id_seccion} a '{nombre_seccion}'"
                )
                
                flash('Sección actualizada exitosamente.', 'success')
                return redirect(url_for('admin_catalogo.listar_secciones'))
                
            except Exception as e:
                current_app.logger.error(f"Error al actualizar sección: {e}")
                flash(f'Error al actualizar la sección: {str(e)}', 'danger')
        
        return render_template('admin/catalogos/editar_seccion.html', seccion=seccion)
        
    except Exception as e:
        current_app.logger.error(f"Error al editar sección: {e}")
        flash('Error al cargar la sección.', 'danger')
        return redirect(url_for('admin_catalogo.listar_secciones'))


@admin_catalogo_bp.route('/secciones/eliminar/<int:id_seccion>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def eliminar_seccion(id_seccion):
    """Elimina una sección de legajo."""
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        audit_service = current_app.config['AUDIT_SERVICE']
        
        seccion = legajo_service._personal_repo.get_seccion_by_id(id_seccion)
        if not seccion:
            flash('Sección no encontrada.', 'danger')
            return redirect(url_for('admin_catalogo.listar_secciones'))
        
        legajo_service._personal_repo.delete_seccion(id_seccion)
        
        audit_service.log(
            current_user.id,
            'Catálogos',
            'ELIMINAR_SECCION',
            f"Eliminó la sección '{seccion['nombre_seccion']}' (ID {id_seccion})"
        )
        
        flash('Sección eliminada exitosamente.', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error al eliminar sección: {e}")
        flash(f'Error al eliminar la sección. Puede estar en uso: {str(e)}', 'danger')
    
    return redirect(url_for('admin_catalogo.listar_secciones'))


# =====================================================================
# GESTIÓN DE TIPOS DE DOCUMENTO
# =====================================================================

@admin_catalogo_bp.route('/tipos-documento')
@login_required
@role_required('AdministradorLegajos')
def listar_tipos_documento():
    """Lista todos los tipos de documento."""
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        tipos_documento = legajo_service._personal_repo.get_all_tipos_documento()
        return render_template('admin/catalogos/listar_tipos_documento.html', tipos_documento=tipos_documento)
    except Exception as e:
        current_app.logger.error(f"Error al listar tipos de documento: {e}")
        flash('Error al cargar los tipos de documento.', 'danger')
        return redirect(url_for('legajo.dashboard'))


@admin_catalogo_bp.route('/tipos-documento/nuevo', methods=['GET', 'POST'])
@login_required
@role_required('AdministradorLegajos')
def crear_tipo_documento():
    """Crea un nuevo tipo de documento."""
    if request.method == 'POST':
        nombre_tipo = request.form.get('nombre_tipo', '').strip()
        
        if not nombre_tipo:
            flash('El nombre del tipo de documento es obligatorio.', 'danger')
            return render_template('admin/catalogos/crear_tipo_documento.html')
        
        try:
            legajo_service = current_app.config['LEGAJO_SERVICE']
            audit_service = current_app.config['AUDIT_SERVICE']
            
            new_id = legajo_service._personal_repo.create_tipo_documento(nombre_tipo)
            
            audit_service.log(
                current_user.id,
                'Catálogos',
                'CREAR_TIPO_DOCUMENTO',
                f"Creó el tipo de documento '{nombre_tipo}' con ID {new_id}"
            )
            
            flash(f'Tipo de documento "{nombre_tipo}" creado exitosamente.', 'success')
            return redirect(url_for('admin_catalogo.listar_tipos_documento'))
            
        except Exception as e:
            current_app.logger.error(f"Error al crear tipo de documento: {e}")
            flash(f'Error al crear el tipo de documento: {str(e)}', 'danger')
    
    return render_template('admin/catalogos/crear_tipo_documento.html')


@admin_catalogo_bp.route('/tipos-documento/editar/<int:id_tipo>', methods=['GET', 'POST'])
@login_required
@role_required('AdministradorLegajos')
def editar_tipo_documento(id_tipo):
    """Edita un tipo de documento existente."""
    legajo_service = current_app.config['LEGAJO_SERVICE']
    
    try:
        tipo_documento = legajo_service._personal_repo.get_tipo_documento_by_id(id_tipo)
        if not tipo_documento:
            flash('Tipo de documento no encontrado.', 'danger')
            return redirect(url_for('admin_catalogo.listar_tipos_documento'))
        
        # Obtener secciones asociadas
        secciones_asociadas = legajo_service._personal_repo.get_secciones_by_tipo_documento(id_tipo)
        todas_secciones = legajo_service._personal_repo.get_all_secciones()
        
        if request.method == 'POST':
            nombre_tipo = request.form.get('nombre_tipo', '').strip()
            
            if not nombre_tipo:
                flash('El nombre del tipo de documento es obligatorio.', 'danger')
                return render_template('admin/catalogos/editar_tipo_documento.html', 
                                     tipo_documento=tipo_documento,
                                     secciones_asociadas=secciones_asociadas,
                                     todas_secciones=todas_secciones)
            
            try:
                audit_service = current_app.config['AUDIT_SERVICE']
                legajo_service._personal_repo.update_tipo_documento(id_tipo, nombre_tipo)
                
                audit_service.log(
                    current_user.id,
                    'Catálogos',
                    'ACTUALIZAR_TIPO_DOCUMENTO',
                    f"Actualizó el tipo de documento ID {id_tipo} a '{nombre_tipo}'"
                )
                
                flash('Tipo de documento actualizado exitosamente.', 'success')
                return redirect(url_for('admin_catalogo.listar_tipos_documento'))
                
            except Exception as e:
                current_app.logger.error(f"Error al actualizar tipo de documento: {e}")
                flash(f'Error al actualizar el tipo de documento: {str(e)}', 'danger')
        
        return render_template('admin/catalogos/editar_tipo_documento.html', 
                             tipo_documento=tipo_documento,
                             secciones_asociadas=secciones_asociadas,
                             todas_secciones=todas_secciones)
        
    except Exception as e:
        current_app.logger.error(f"Error al editar tipo de documento: {e}")
        flash('Error al cargar el tipo de documento.', 'danger')
        return redirect(url_for('admin_catalogo.listar_tipos_documento'))


@admin_catalogo_bp.route('/tipos-documento/eliminar/<int:id_tipo>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def eliminar_tipo_documento(id_tipo):
    """Elimina un tipo de documento."""
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        audit_service = current_app.config['AUDIT_SERVICE']
        
        tipo_documento = legajo_service._personal_repo.get_tipo_documento_by_id(id_tipo)
        if not tipo_documento:
            flash('Tipo de documento no encontrado.', 'danger')
            return redirect(url_for('admin_catalogo.listar_tipos_documento'))
        
        legajo_service._personal_repo.delete_tipo_documento(id_tipo)
        
        audit_service.log(
            current_user.id,
            'Catálogos',
            'ELIMINAR_TIPO_DOCUMENTO',
            f"Eliminó el tipo de documento '{tipo_documento['nombre_tipo']}' (ID {id_tipo})"
        )
        
        flash('Tipo de documento eliminado exitosamente.', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error al eliminar tipo de documento: {e}")
        flash(f'Error al eliminar el tipo de documento. Puede estar en uso: {str(e)}', 'danger')
    
    return redirect(url_for('admin_catalogo.listar_tipos_documento'))


# =====================================================================
# API PARA GESTIONAR RELACIÓN TIPO_DOCUMENTO - SECCIÓN
# =====================================================================

@admin_catalogo_bp.route('/api/tipos-documento/<int:id_tipo>/agregar-seccion', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def agregar_seccion_a_tipo(id_tipo):
    """Asocia una sección a un tipo de documento."""
    try:
        id_seccion = request.form.get('id_seccion', type=int)
        
        if not id_seccion:
            return jsonify({'success': False, 'message': 'ID de sección no proporcionado'}), 400
        
        legajo_service = current_app.config['LEGAJO_SERVICE']
        audit_service = current_app.config['AUDIT_SERVICE']
        
        resultado = legajo_service._personal_repo.add_tipo_documento_to_seccion(id_tipo, id_seccion)
        
        if resultado:
            audit_service.log(
                current_user.id,
                'Catálogos',
                'ASOCIAR_TIPO_SECCION',
                f"Asoció el tipo de documento ID {id_tipo} con la sección ID {id_seccion}"
            )
            return jsonify({'success': True, 'message': 'Sección agregada exitosamente'})
        else:
            return jsonify({'success': False, 'message': 'La asociación ya existe'}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error al agregar sección a tipo: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_catalogo_bp.route('/api/tipos-documento/<int:id_tipo>/remover-seccion/<int:id_seccion>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def remover_seccion_de_tipo(id_tipo, id_seccion):
    """Elimina la asociación entre un tipo de documento y una sección."""
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        audit_service = current_app.config['AUDIT_SERVICE']
        
        resultado = legajo_service._personal_repo.remove_tipo_documento_from_seccion(id_tipo, id_seccion)
        
        if resultado:
            audit_service.log(
                current_user.id,
                'Catálogos',
                'DESASOCIAR_TIPO_SECCION',
                f"Eliminó la asociación del tipo de documento ID {id_tipo} con la sección ID {id_seccion}"
            )
            return jsonify({'success': True, 'message': 'Sección removida exitosamente'})
        else:
            return jsonify({'success': False, 'message': 'La asociación no existe'}), 404
            
    except Exception as e:
        current_app.logger.error(f"Error al remover sección de tipo: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
