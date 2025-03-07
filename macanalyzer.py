import re
import requests
import os
import sys
from colorama import init, Fore, Style, Back

# Inicializar colorama para soportar colores en la terminal
init(autoreset=True)

def download_oui_database(url="https://standards-oui.ieee.org/oui/oui.txt"):
    """Descarga la base de datos OUI desde IEEE."""
    try:
        print(f"{Fore.YELLOW}Descargando base de datos OUI desde {url}...")
        response = requests.get(url)
        response.raise_for_status()
        print(f"{Fore.GREEN}Base de datos descargada correctamente.")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error al descargar la base de datos: {e}")
        return None

def parse_oui_database(data):
    """Analiza la base de datos OUI y crea un diccionario de prefijos a fabricantes."""
    if not data:
        return {}
    
    oui_dict = {}
    
    # Patrón para extraer el prefijo OUI y el nombre del fabricante
    pattern = r'([0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2})\s+\(hex\)\s+(.*)'
    
    for line in data.splitlines():
        match = re.search(pattern, line)
        if match:
            oui, manufacturer = match.groups()
            # Normalizamos el OUI a formato sin guiones y en minúsculas
            oui = oui.replace('-', '').lower()
            oui_dict[oui] = manufacturer.strip()
    
    return oui_dict

def parse_mac_address(mac):
    """Analiza una dirección MAC y extrae su OUI y flags."""
    # Normaliza la dirección MAC eliminando separadores y convirtiendo a minúsculas
    mac = re.sub(r'[.:-]', '', mac).lower()
    
    if not re.match(r'^[0-9a-f]{12}$', mac):
        return None, None
    
    oui = mac[:6]  # Los primeros 6 caracteres (3 bytes) son el OUI
    
    # Análisis de flags en el primer byte
    first_byte = int(mac[0:2], 16)
    flags = {
        'U/L': bool(first_byte & 0x02),  # Bit Universal/Local
        'I/G': bool(first_byte & 0x01)   # Bit Individual/Group
    }
    
    return oui, flags

def explain_flags(flags):
    """Explica el significado de las flags de la dirección MAC."""
    explanations = []
    
    if 'U/L' in flags:
        if flags['U/L']:
            explanations.append(f"{Fore.CYAN}U/L: {Fore.RED}1{Style.RESET_ALL} - Esta es una dirección {Fore.RED}administrada localmente (LAA)")
        else:
            explanations.append(f"{Fore.CYAN}U/L: {Fore.GREEN}0{Style.RESET_ALL} - Esta es una dirección {Fore.GREEN}administrada universalmente (UAA)")
    
    if 'I/G' in flags:
        if flags['I/G']:
            explanations.append(f"{Fore.CYAN}I/G: {Fore.RED}1{Style.RESET_ALL} - Esta es una dirección de {Fore.RED}grupo/multicast")
        else:
            explanations.append(f"{Fore.CYAN}I/G: {Fore.GREEN}0{Style.RESET_ALL} - Esta es una dirección {Fore.GREEN}individual/unicast")
    
    return explanations

def analyze_mac(mac_address, oui_database):
    """Analiza una dirección MAC y devuelve información sobre su fabricante y flags."""
    oui, flags = parse_mac_address(mac_address)
    
    if not oui:
        return {
            "error": "Formato de dirección MAC inválido",
            "example": "Formatos válidos: 00:11:22:33:44:55, 00-11-22-33-44-55, 001122334455"
        }
    
    manufacturer = oui_database.get(oui, "Fabricante desconocido")
    flag_explanations = explain_flags(flags)
    
    return {
        "mac": mac_address,
        "oui": ':'.join([oui[i:i+2] for i in range(0, 6, 2)]),
        "manufacturer": manufacturer,
        "flags": flags,
        "flag_explanations": flag_explanations
    }

def show_flags_explanation():
    """Muestra una explicación detallada de las flags de direcciones MAC."""
    print(f"\n{Back.BLUE}{Fore.WHITE} EXPLICACIÓN DE FLAGS EN DIRECCIONES MAC {Style.RESET_ALL}")
    print(f"""
{Fore.YELLOW}Las direcciones MAC contienen dos flags importantes en el primer byte:

{Fore.CYAN}1. Flag U/L (Universal/Local) - Segundo bit del primer byte:
   {Fore.GREEN}- 0: Dirección administrada universalmente (UAA)
        Asignada por el fabricante y globalmente única
        Es la dirección original de fábrica
   {Fore.RED}- 1: Dirección administrada localmente (LAA)
        Modificada o asignada por un administrador de red
        No garantiza unicidad global

{Fore.CYAN}2. Flag I/G (Individual/Group) - Primer bit del primer byte:
   {Fore.GREEN}- 0: Dirección individual (unicast)
        Destinada a un único dispositivo receptor
   {Fore.RED}- 1: Dirección de grupo (multicast/broadcast)
        Recibida por múltiples dispositivos
        La dirección FF:FF:FF:FF:FF:FF es broadcast (todos los dispositivos)

{Fore.YELLOW}Estas flags son útiles para identificar direcciones modificadas y
determinar si un paquete va dirigido a uno o múltiples dispositivos.
    """)
    input(f"\n{Fore.YELLOW}Presiona Enter para continuar...{Style.RESET_ALL}")

def display_result(result):
    """Muestra el resultado del análisis de una dirección MAC con formato y colores."""
    if "error" in result:
        print(f"{Fore.RED}Error: {result['error']}")
        print(f"{Fore.YELLOW}Ejemplo: {result['example']}")
        return False
    
    print(f"\n{Back.WHITE}{Fore.BLACK} ANÁLISIS DE MAC {Style.RESET_ALL}")
    print(f"{Fore.WHITE}Dirección MAC: {Fore.CYAN}{result['mac']}")
    print(f"{Fore.WHITE}OUI: {Fore.YELLOW}{result['oui']}")
    print(f"{Fore.WHITE}Fabricante: {Fore.GREEN}{result['manufacturer']}")
    
    print(f"\n{Fore.WHITE}Flags:")
    for explanation in result['flag_explanations']:
        print(f"  {explanation}")
    
    return True

def analyze_file(file_path, oui_database):
    """Analiza un archivo con múltiples direcciones MAC, una por línea."""
    try:
        with open(file_path, 'r') as file:
            macs = file.readlines()
    except Exception as e:
        print(f"{Fore.RED}Error al abrir el archivo: {e}")
        return
    
    print(f"{Fore.YELLOW}Analizando {len(macs)} direcciones MAC del archivo: {file_path}")
    
    results = []
    success_count = 0
    error_count = 0
    
    for mac in macs:
        mac = mac.strip()
        if not mac or mac.startswith('#'):  # Ignora líneas vacías y comentarios
            continue
        
        result = analyze_mac(mac, oui_database)
        results.append(result)
        
        if "error" in result:
            error_count += 1
        else:
            success_count += 1
    
    # Mostrar resultados
    print(f"\n{Back.BLUE}{Fore.WHITE} RESULTADOS DEL ANÁLISIS EN BLOQUE {Style.RESET_ALL}")
    print(f"{Fore.GREEN}Direcciones analizadas correctamente: {success_count}")
    print(f"{Fore.RED}Errores de formato: {error_count}")
    
    # Preguntar si quiere ver todos los resultados
    show_all = input(f"\n{Fore.YELLOW}¿Desea ver todos los resultados detallados? (s/n): {Style.RESET_ALL}").lower() == 's'
    
    if show_all:
        for i, result in enumerate(results, 1):
            print(f"\n{Fore.CYAN}===== Resultado {i} =====")
            display_result(result)
    
    # Preguntar si quiere guardar resultados en un archivo
    save_to_file = input(f"\n{Fore.YELLOW}¿Desea guardar los resultados en un archivo? (s/n): {Style.RESET_ALL}").lower() == 's'
    
    if save_to_file:
        output_file = input(f"{Fore.YELLOW}Nombre del archivo de salida: {Style.RESET_ALL}")
        try:
            with open(output_file, 'w') as f:
                f.write("ANÁLISIS DE DIRECCIONES MAC\n")
                f.write("==========================\n\n")
                
                for i, result in enumerate(results, 1):
                    f.write(f"Resultado {i}:\n")
                    if "error" in result:
                        f.write(f"  Error: {result['error']}\n")
                    else:
                        f.write(f"  MAC: {result['mac']}\n")
                        f.write(f"  OUI: {result['oui']}\n")
                        f.write(f"  Fabricante: {result['manufacturer']}\n")
                        f.write("  Flags:\n")
                        for explanation in result['flag_explanations']:
                            # Quitar códigos de color para el archivo
                            clean_exp = re.sub(r'\x1b\[\d+m', '', explanation)
                            f.write(f"    - {clean_exp}\n")
                    f.write("\n")
                
            print(f"{Fore.GREEN}Resultados guardados en: {output_file}")
        except Exception as e:
            print(f"{Fore.RED}Error al guardar los resultados: {e}")

def display_menu():
    """Muestra el menú principal del programa."""
    print(f"\n{Back.BLUE}{Fore.WHITE} MENÚ PRINCIPAL {Style.RESET_ALL}")
    print(f"{Fore.CYAN}1.{Fore.WHITE} Analizar una dirección MAC individual")
    print(f"{Fore.CYAN}2.{Fore.WHITE} Analizar múltiples direcciones MAC desde un archivo")
    print(f"{Fore.CYAN}3.{Fore.WHITE} Ver explicación de flags")
    print(f"{Fore.CYAN}s.{Fore.WHITE} Salir")
    return input(f"\n{Fore.YELLOW}Seleccione una opción: {Style.RESET_ALL}").lower()

def display_welcome():
    """Muestra el mensaje de bienvenida y el título del programa."""
    os.system('cls' if os.name == 'nt' else 'clear')  # Limpiar pantalla
    print(f"""
{Back.CYAN}{Fore.BLACK} ╔═══════════════════════════════════════════╗ {Style.RESET_ALL}
{Back.CYAN}{Fore.BLACK} ║               MAC ANALYZER                ║ {Style.RESET_ALL}
{Back.CYAN}{Fore.BLACK} ╚═══════════════════════════════════════════╝ {Style.RESET_ALL}
""")
    print(f"{Fore.YELLOW}Herramienta para analizar direcciones MAC y determinar fabricantes")
    print(f"{Fore.YELLOW}Basado en la base de datos OUI del IEEE")

def main():
    """Función principal que ejecuta el analizador de MAC."""
    # Mostrar pantalla de bienvenida
    display_welcome()
    
    print(f"{Fore.CYAN}Iniciando programa...")
    
    # Instalar dependencias si no están instaladas
    try:
        import colorama
    except ImportError:
        print(f"{Fore.YELLOW}Instalando dependencias necesarias...")
        os.system('pip install colorama')
    
    # Descargar y procesar la base de datos OUI
    oui_data = download_oui_database()
    if not oui_data:
        print(f"{Fore.RED}No se pudo descargar la base de datos OUI. Saliendo.")
        return
    
    print(f"{Fore.YELLOW}Procesando base de datos OUI...")
    oui_database = parse_oui_database(oui_data)
    print(f"{Fore.GREEN}Base de datos cargada con {len(oui_database)} entradas.")
    
    # Mostrar explicación de flags al inicio
    show_flags_explanation()
    
    while True:
        option = display_menu()
        
        if option == 's':
            print(f"{Fore.GREEN}¡Gracias por usar MAC Analyzer! ¡Hasta pronto!")
            break
        elif option == '1':
            mac_address = input(f"\n{Fore.YELLOW}Introduce una dirección MAC: {Style.RESET_ALL}")
            result = analyze_mac(mac_address, oui_database)
            display_result(result)
        elif option == '2':
            file_path = input(f"\n{Fore.YELLOW}Introduce la ruta del archivo con direcciones MAC: {Style.RESET_ALL}")
            analyze_file(file_path, oui_database)
        elif option == '3':
            show_flags_explanation()
        else:
            print(f"{Fore.RED}Opción no válida. Inténtalo de nuevo.")
        
        input(f"\n{Fore.YELLOW}Presiona Enter para continuar...{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Programa interrumpido por el usuario. ¡Hasta pronto!")
    except Exception as e:
        print(f"{Fore.RED}Error inesperado: {e}")
