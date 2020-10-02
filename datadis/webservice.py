# -*- coding: utf-8 -*-
import requests
import logging
import json
from os import path
from datadis.validators import validar_contrato
from datadis.adaptors import adaptar_datos_contrato, adaptar_maximas_potencia
from datetime import datetime

BASE_URL = "https://apihsdistribuidoras.asemeservicios.com"
HEADER = {
    'Content-Type': 'application/json', 'Accept-Charset': 'utf-8', 'charset': 'utf-8'
}
logger = logging.getLogger('Datadis Webservice')

class DatadisWebserviceController(object):

    def __init__(self):
        pass

    @property
    def templates(self):
        return path.join(path.dirname(path.realpath(__file__)), 'templates/')

    @property
    def token(self):
        return 'Bearer ' + self.token

    @property
    def url_autenticar(self):
        return BASE_URL + '/autenticar'

    @property
    def url_contrato(self):
        return BASE_URL + '/contrato'

    @property
    def url_eliminar_contrato(self):
        return BASE_URL + '/contrato/{nif}/{cups}'

    @property
    def url_bloquear_consumidor(self):
        return BASE_URL + '/consumidor/bloquear'

    @property
    def url_maximas_potencia(self):
        return BASE_URL + '/maximaspotencia'

    @property
    def url_estado(self):
        return BASE_URL + '/estado/{timestamp}/{guid}'

    def autenticar(self, user, password):
        """Autenticarse en el sistema DATADIS.
        Enviar un diccionario con las claves requeridas indicadas a continuacion
        user: Usuario
        password: Clave
        """
        user = str(user).zfill(4)
        r = requests.post(self.url_autenticar, headers=HEADER, json={'usuario': user, 'contraseña': password})
        if r.status_code == 200:
            resp_data = r.json()
            api_token = resp_data.get('token', '')
            username = resp_data.get('usuario', '')
            logger.info('User {} is now connected'.format(username))
            self.token = api_token
            self.user = username
            HEADER['Authorization'] = self.token
            return resp_data
        else:
            raise Exception(r.content)

    def contrato(self, data, method='POST'):
        """Publicar contrato al sistema DATADIS.
        Si el contrato ya existe en el sistema, se modificara
        Enviar un diccionario con las claves requeridas indicadas a continuacion
        data: {
            "nif": "",
            "nombre": "",
            "comercializadora": "",
            "tensionConexion": "",
            "tarifaAcceso": "",
            "discriminacionHoraria": "",
            "tipoPunto": "",
            "modoControlPotencia": "",
            "fechaInicioContrato": "",
            "cups": "",
            "distribuidora": "",
            "codigoPostal": "",
            "provincia": "",
            "municipio": ""
        }
        method: 'POST' por defecto, utilizar 'DELETE' para eliminar contrato
        return: dict {'guid': identificador de la peticion, 'timestamp': marca de tiempo}
        """
        if method.upper() == 'POST':
            data = adaptar_datos_contrato(data)
            validar_contrato(data)

            with open(self.templates + 'contrato.json') as json_template:
                template = json.load(json_template)
            for key in data.keys():
                if key in template['contrato']:
                    template['contrato'].update({key: data[key]})
                if key in template['puntoSuministro']:
                    template['puntoSuministro'].update({key: data[key]})
                if key in template['titular']:
                    template['titular'].update({key: data[key]})
            r = requests.post(self.url_contrato, headers=HEADER, json=template)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 422:
                raise Exception("No se ha podido publicar el contrato: \n{}".format(r.content))
            else:
                raise Exception("No se ha podido publicar el contrato {}".format(r.status_code))
        if method.upper() == 'DELETE':
            return self.eliminar_contrato(data)

    def eliminar_contrato(self, data):
        """Eliminar un contrato del sistema DATADIS.
        El sistema borrara todos los contratos del mismo NIF y CUPS
        Enviar un diccionario con las claves requeridas indicadas a continuacion
        data: {
            "nif": "",
            "cups": ""
        }
        """
        if 'nif' in data and 'cups' in data:
            r = requests.delete(self.url_eliminar_contrato.format(**data), headers=HEADER)
            if r.status_code == 200:
                return r.json()
            else:
                raise Exception("No se ha podido eliminar el contrato: {}".format(r.status_code))
        else:
            raise KeyError("nif y/o cups no especificados!")

    def maximas_potencia(self, data):
        """Publicar maximetros al sistema DATADIS.
        Enviar un diccionario con las siguiente estructura:
        data: {
            "cups": CON 22 CARACTERES,
            "fecha": AAAA-MM-DD HH:MM, si no se especifica la hora se utilizara 00:00,
            "medida": kWh,
        }
        return: dict {'guid': identificador de la peticion, 'timestamp': marca de tiempo}
        """
        with open(self.templates + 'maximaspotencia.json') as json_template:
            template = json.load(json_template)
        data = adaptar_maximas_potencia(data)
        template['cups'] = data['cups']
        template['registros'][0]['fecha'] = data['fecha']
        template['registros'][0]['hora'] = data['hora']
        template['registros'][0]['medida'] = data['medida']
        r = requests.post(self.url_maximas_potencia, headers=HEADER, json=json.dumps(data))
        if r.status_code == 200:
            return r.json()
        else:
            raise Exception("No se han podido cargar el maximetro: {}".format(r.status_code))

    def bloquear_consumidor(self, nif):
        """Bloquear el acceso a la informacion del sistema DATADIS a un consumidor.
        nif: string indicando el NIF del consumidor
        """
        data = {'nif': nif, 'bloqueado': 'true'}
        r = requests.post(self.url_bloquear_consumidor(), headers=HEADER, json=json.dumps(data))
        if r.status_code == 200:
            return r.json()
        else:
            raise Exception("No se ha podido bloquear el acceso al consumidor: {}".format(r.status_code))

    def estado(self, data):
        """Consultar el estado de una peticion enviada al sistema DATADIS.
        Enviar un diccionario con las siguientes claves:
        data: {
            "guid": 'Codigo de la peticion,
            "timestamp": "Fecha de la peticion"
        }
        return: []
        """
        data = adaptar_estado(data)
        r = requests.post(self.url_estado.format(**data), headers=HEADER)
        if r.status_code == 200:
            resp_data = r.json()
            if resp_data["erroresAcumulados"]:
                return resp_data["erroresAcumulados"]
            return resp_data["ultimaPeticionProcesada"]
        elif r.status_code == 422:
            raise Exception("Error en el formato de datos de la peticion: \n{}".format(r.content))
        else:
            raise Exception("No se ha podido consultar el estado de la peticion: {}".format(r.status_code))
