import pymupdf
import re
import os
import glob
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import json


@dataclass
class EssentialInfo:
    """Informações essenciais para identificação do exame"""
    patient_id: str = ""
    patient_name: str = ""
    study_id: str = ""
    accession_number: str = ""
    study_date: str = ""
    birth_date: str = ""
    sex: str = ""


@dataclass
class XRaySourceParams:
    identification: str = ""
    kvp: str = ""
    max_tube_current: str = ""
    tube_current: str = ""
    exposure_time_per_rotation: Optional[str] = None


@dataclass
class CTDose:
    mean_ctdivol: str = ""
    phantom_type: str = ""
    dlp: str = ""
    size_specific_dose: Optional[str] = None
    ctdivol_alert_value: Optional[str] = None


@dataclass
class CTAcquisitionParams:
    exposure_time: str = ""
    scanning_length: str = ""
    nominal_single_collimation: str = ""
    nominal_total_collimation: str = ""
    num_xray_sources: str = ""
    pitch_factor: Optional[str] = None


@dataclass
class CTAcquisition:
    protocol: str = ""
    target_region: str = ""
    acquisition_type: str = ""
    procedure_context: str = ""
    irradiation_event_uid: str = ""
    comment: str = ""
    acquisition_params: CTAcquisitionParams = None
    xray_source_params: XRaySourceParams = None
    ct_dose: CTDose = None


@dataclass
class IrradiationInfo:
    start_time: str = ""
    end_time: str = ""
    total_events: str = ""
    total_dlp: str = ""


@dataclass
class DeviceInfo:
    observer_name: str = ""
    manufacturer: str = ""
    model_name: str = ""
    serial_number: str = ""
    physical_location: str = ""


@dataclass
class CTScanReportMinimal:
    # Informações básicas para identificação
    hospital: str = ""
    report_date: str = ""

    # Dados essenciais para identificação
    essential: EssentialInfo = None

    # Dados técnicos
    device: DeviceInfo = None
    irradiation: IrradiationInfo = None
    acquisitions: List[CTAcquisition] = None

    def __post_init__(self):
        if self.essential is None:
            self.essential = EssentialInfo()
        if self.device is None:
            self.device = DeviceInfo()
        if self.irradiation is None:
            self.irradiation = IrradiationInfo()
        if self.acquisitions is None:
            self.acquisitions = []


class CTReportExtractorMinimal:
    def __init__(self):
        # Padrões MÚLTIPLOS para cada identificador essencial
        # Isso aumenta as chances de capturar os dados mesmo com formatação estranha
        self.essential_patterns = {
            'patient_id': [
                r'Patient\s*ID:\s*(\d+)',
                r'PatientID:\s*(\d+)',
                r'Patient\s*ID\s*:\s*(\d+)',
            ],
            'study_id': [
                r'Study\s*ID:\s*(\d+)',
                r'StudyID:\s*(\d+)',
                r'Study\s*ID\s*:\s*(\d+)'
            ],
            'accession_number': [
                r'Accession\s*Number:\s*(\d+)',
                r'AccessionNumber:\s*(\d+)',
                r'Accession\s*Number\s*:\s*(\d+)'
            ],
            'study_date': [
                r'Study\s*Date:\s*([^\\n]+?)(?=\n|$)',
                r'StudyDate:\s*([^\\n]+?)(?=\n|$)',
                r'Study\s*Date\s*:\s*([^\\n]+?)(?=\n|$)'
            ],
            'birth_date': [
                r"Patient's\s*Birth\s*Date:\s*([^\\n]+?)(?=\n|$)",
                r"Patient's\s*Birth\s*Date\s*:\s*([^\\n]+?)(?=\n|$)",
                r"Birth\s*Date:\s*([^\\n]+?)(?=\n|$)",
                r"BirthDate:\s*([^\\n]+?)(?=\n|$)"
            ],
            'sex': [
                r"Patient's\s*Sex:\s*(\w+)",
                r"Patient's\s*Sex\s*:\s*(\w+)",
                r"Sex:\s*(\w+)",
                r"Gender:\s*(\w+)"
            ]
        }

        # Padrões para dados técnicos (mantidos)
        self.technical_patterns = {
            # Dispositivo
            'device_name': r"Device Observer Name:\s*(.+)",
            'manufacturer': r"Device Observer Manufacturer:\s*(.+)",
            'model_name': r"Device Observer Model Name:\s*(.+)",
            'serial_number': r"Device Observer Serial Number:\s*(.+)",
            'location': r"Device Observer Physical Location during observation:\s*(.+)",

            # Irradiação (com unidades)
            'start_irradiation': r"Start of X-Ray Irradiation:\s*(.+)",
            'end_irradiation': r"End of X-Ray Irradiation:\s*(.+)",
            'total_events': r"Total Number of Irradiation Events\s*=\s*([\d.]+\s*events)",
            'total_dlp': r"CT Dose Length Product Total\s*=\s*([\d.]+\s*mGy\.cm)",

            # Aquisições
            'protocol': r"Acquisition Protocol:\s*(.+)",
            'target_region': r"Target Region:\s*(.+)",
            'acquisition_type': r"CT Acquisition Type:\s*(.+)",
            'procedure_context': r"Procedure Context:\s*(.+)",
            'irradiation_uid': r"Irradiation Event UID:\s*(.+)",
            'comment': r"Comment:\s*(.+)",

            # Parâmetros de aquisição (com unidades)
            'exposure_time': r"Exposure Time\s*=\s*([\d.]+\s*s)",
            'scanning_length': r"Scanning Length\s*=\s*([\d.]+\s*mm)",
            'single_collimation': r"Nominal Single Collimation Width\s*=\s*([\d.]+\s*mm)",
            'total_collimation': r"Nominal Total Collimation Width\s*=\s*([\d.]+\s*mm)",
            'num_sources': r"Number of X-Ray Sources\s*=\s*([\d.]+\s*X-Ray sources)",
            'pitch_factor': r"Pitch Factor\s*=\s*([\d.]+\s*ratio)",

            # Fonte de raios-X (com unidades)
            'source_id': r"Identification of the X-Ray Source:\s*(.+)",
            'kvp': r"KVP\s*=\s*([\d.]+\s*kV)",
            'max_current': r"Maximum X-Ray Tube Current\s*=\s*([\d.]+\s*mA)",
            'tube_current': r"(?<!Maximum )X-Ray Tube Current\s*=\s*([\d.]+\s*mA)",
            'rotation_time': r"Exposure Time per Rotation\s*=\s*([\d.]+\s*s)",

            # Dose (com unidades)
            'mean_ctdivol': r"Mean CTDIvol\s*=\s*([\d.]+\s*mGy)",
            'phantom_type': r"CTDIw Phantom Type:\s*(.+)",
            'dlp': r"DLP\s*=\s*([\d.]+\s*mGy\.cm)",
            'specific_dose': r"Size Specific Dose Estimation\s*=\s*([\d.]+\s*mGy)",
            'alert_value': r"CTDIvol Alert Value\s*=\s*([\d.]+\s*mGy)"
        }

    def clean_extracted_text(self, text: str) -> str:
        """
        ✨ FUNÇÃO DE LIMPEZA: Remove apenas caracteres invisíveis problemáticos

        Remove APENAS:
        - NNBSP (Non-Breaking Space)
        - Zero-width spaces
        - Outros espaços Unicode invisíveis
        - Espaços duplos/triplos
        - Correção específica para horários (espaço após :)

        NÃO mexe com pontuação normal de números/unidades!
        """
        if not text:
            return ""

        cleaned = text

        # Remove APENAS NNBSP e caracteres invisíveis
        cleaned = cleaned.replace('\u00A0', ' ')  # Non-Breaking Space
        cleaned = cleaned.replace('NNBSP', ' ')  # NNBSP literal (caso apareça assim)

        # Remove outros espaços Unicode INVISÍVEIS (apenas os problemáticos)
        cleaned = cleaned.replace('\u2000', ' ')  # En Quad
        cleaned = cleaned.replace('\u2001', ' ')  # Em Quad
        cleaned = cleaned.replace('\u2002', ' ')  # En Space
        cleaned = cleaned.replace('\u2003', ' ')  # Em Space
        cleaned = cleaned.replace('\u2009', ' ')  # Thin Space
        cleaned = cleaned.replace('\u200A', ' ')  # Hair Space
        cleaned = cleaned.replace('\u202F', ' ')  # Narrow No-Break Space

        # Remove zero-width characters (completamente invisíveis)
        cleaned = cleaned.replace('\u200B', '')  # Zero Width Space
        cleaned = cleaned.replace('\u200C', '')  # Zero Width Non-Joiner
        cleaned = cleaned.replace('\u200D', '')  # Zero Width Joiner
        cleaned = cleaned.replace('\uFEFF', '')  # Zero Width No-Break Space (BOM)

        # ✨ CORREÇÃO ESPECÍFICA: Remove espaço extra após : em horários (ex: "2:40: 38" → "2:40:38")
        # Mas APENAS em contexto de horário (números:números)
        cleaned = re.sub(r'(\d+:\d+):\s+(\d+)', r'\1:\2', cleaned)

        # APENAS normaliza espaços múltiplos (não mexe com pontuação!)
        cleaned = re.sub(r'  +', ' ', cleaned)  # Substitui 2+ espaços por 1 espaço

        return cleaned.strip()

    def extract_hospital_info(self, text: str) -> tuple:
        """Extrai informações do hospital e data do relatório"""
        lines = text.split('\n')
        hospital = ""
        report_date = ""

        for line in lines[:5]:
            if "Hospital" in line and "on CT" in line:
                parts = line.split("on CT,")
                if len(parts) >= 2:
                    hospital = parts[0].replace("By ", "").strip()
                    report_date = self.clean_extracted_text(parts[1].strip())
                break

        return hospital, report_date

    def extract_patient_name(self, text: str) -> str:
        """Extrai o nome do paciente usando PyMuPDF + Limpeza"""

        lines = text.split('\n')
        patient_name_parts = []

        for i, line in enumerate(lines):
            # Procura pela linha que contém "Patient's Name:"
            line_stripped = line.strip()
            if re.search(r"Patient's\s*Name\s*:", line_stripped, re.IGNORECASE):
                # Extrai o que vem depois de "Patient's Name:"
                name_part = re.sub(r".*Patient's\s*Name\s*:\s*", "", line_stripped, flags=re.IGNORECASE).strip()
                if name_part:
                    # ✨ LIMPA caracteres problemáticos
                    name_part = self.clean_extracted_text(name_part)
                    patient_name_parts.append(name_part)

                # Com PyMuPDF, verifica as próximas linhas para capturar continuação do nome
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()

                    # Para se encontrar uma linha vazia
                    if not next_line:
                        break

                    # Para se encontrar outro campo (que contém ':')
                    if ':' in next_line:
                        break

                    # Para se encontrar um campo conhecido do paciente
                    known_fields = ['Patient ID', 'PatientID', 'Patient\'s Birth', 'Patient\'s Sex']
                    if any(field in next_line for field in known_fields):
                        break

                    # Se chegou até aqui, provavelmente é continuação do nome
                    # ✨ LIMPA caracteres problemáticos
                    next_line_clean = self.clean_extracted_text(next_line)
                    patient_name_parts.append(next_line_clean)
                    j += 1

                break

        # Junta todas as partes do nome e limpa
        if patient_name_parts:
            full_name = ' '.join(patient_name_parts).strip()
            # Remove espaços duplos (redundante, mas garantia extra)
            full_name = re.sub(r'\s+', ' ', full_name)
            return full_name

        return ""

    def extract_study_date_clean(self, text: str) -> str:
        """
        ✨ MÉTODO MELHORADO: Extrai Study Date e limpa caracteres problemáticos

        Com PyMuPDF pode vir assim:
        Study Date: May 13, 2025, 2:40:
        38 PM

        Ou com NNBSP: "May 13, 2025, 2:40:NNBSP38 PM"
        """

        lines = text.split('\n')

        for i, line in enumerate(lines):
            if re.search(r'Study\s*Date\s*:', line, re.IGNORECASE):
                # Pega o que vem depois de "Study Date:"
                date_part = re.sub(r'.*Study\s*Date\s*:\s*', '', line, flags=re.IGNORECASE).strip()

                # Se a linha termina com ":" ou parece incompleta, pega a próxima linha também
                if (date_part.endswith(':') or date_part.endswith(',')) and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not ':' in next_line:
                        date_part = (date_part + ' ' + next_line).strip()

                if date_part:
                    # Limpa caracteres problemáticos
                    date_part = self.clean_extracted_text(date_part)
                    return date_part

        # Fallback para os padrões originais
        raw_date = self.extract_essential_value(text, self.essential_patterns['study_date'])
        return self.clean_extracted_text(raw_date) if raw_date else ""

    def extract_physical_location_multiline(self, text: str) -> str:
        """Extrai physical location mesmo se quebrado em múltiplas linhas"""

        lines = text.split('\n')

        for i, line in enumerate(lines):
            if re.search(r'Device Observer Physical Location during observation:', line, re.IGNORECASE):
                # Pega o que vem depois do campo
                location_part = re.sub(r'.*Device Observer Physical Location during observation:\s*', '', line,
                                       flags=re.IGNORECASE).strip()

                # Se parece truncado (termina abruptamente sem pontuação) e existe próxima linha
                if location_part and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()

                    # Se a próxima linha não é um campo numerado (1.10, 1.11, etc.)
                    # e não contém ":", provavelmente é continuação
                    if (next_line and
                            not re.match(r'^\d+\.\d+', next_line) and  # Não começa com número.número
                            ':' not in next_line and  # Não é outro campo
                            len(next_line) < 50):  # Linha razoavelmente curta (continuação)

                        location_part = (location_part + ' ' + next_line).strip()

                if location_part:
                    return self.clean_extracted_text(location_part)

        # Fallback para o método original
        return self.extract_technical_value(text, self.technical_patterns['location'])

    def extract_essential_value(self, text: str, pattern_list: List[str]) -> str:
        """Tenta extrair valor usando múltiplos padrões até encontrar um"""
        for pattern in pattern_list:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # ✨ LIMPA o resultado antes de retornar
                return self.clean_extracted_text(match.group(1))
        return ""

    def extract_technical_value(self, text: str, pattern: str) -> str:
        """Extrai um valor técnico usando regex"""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # ✨ LIMPA o resultado antes de retornar
            return self.clean_extracted_text(match.group(1))
        return ""

    def extract_ct_acquisitions(self, text: str) -> List[CTAcquisition]:
        """Extrai informações de aquisições CT"""
        acquisitions = []

        # Divide o texto em seções de aquisição
        acquisition_sections = re.split(r'\d+\.\d+\s+CT\s+Acquisition', text)

        for section in acquisition_sections[1:]:
            acquisition = CTAcquisition()

            # Extrai informações básicas da aquisição
            acquisition.protocol = self.extract_technical_value(section, self.technical_patterns['protocol'])
            acquisition.target_region = self.extract_technical_value(section, self.technical_patterns['target_region'])
            acquisition.acquisition_type = self.extract_technical_value(section,
                                                                        self.technical_patterns['acquisition_type'])
            acquisition.procedure_context = self.extract_technical_value(section,
                                                                         self.technical_patterns['procedure_context'])
            acquisition.irradiation_event_uid = self.extract_technical_value(section,
                                                                             self.technical_patterns['irradiation_uid'])
            acquisition.comment = self.extract_technical_value(section, self.technical_patterns['comment'])

            # Extrai parâmetros de aquisição
            params = CTAcquisitionParams()
            params.exposure_time = self.extract_technical_value(section, self.technical_patterns['exposure_time'])
            params.scanning_length = self.extract_technical_value(section, self.technical_patterns['scanning_length'])
            params.nominal_single_collimation = self.extract_technical_value(section, self.technical_patterns[
                'single_collimation'])
            params.nominal_total_collimation = self.extract_technical_value(section, self.technical_patterns[
                'total_collimation'])
            params.num_xray_sources = self.extract_technical_value(section, self.technical_patterns['num_sources'])
            params.pitch_factor = self.extract_technical_value(section, self.technical_patterns['pitch_factor']) or None
            acquisition.acquisition_params = params

            # Extrai parâmetros da fonte de raios-X
            xray_params = XRaySourceParams()
            xray_params.identification = self.extract_technical_value(section, self.technical_patterns['source_id'])
            xray_params.kvp = self.extract_technical_value(section, self.technical_patterns['kvp'])
            xray_params.max_tube_current = self.extract_technical_value(section, self.technical_patterns['max_current'])
            xray_params.tube_current = self.extract_technical_value(section, self.technical_patterns['tube_current'])
            xray_params.exposure_time_per_rotation = self.extract_technical_value(section, self.technical_patterns[
                'rotation_time']) or None
            acquisition.xray_source_params = xray_params

            # Extrai informações de dose
            dose = CTDose()
            dose.mean_ctdivol = self.extract_technical_value(section, self.technical_patterns['mean_ctdivol'])
            dose.phantom_type = self.extract_technical_value(section, self.technical_patterns['phantom_type'])
            dose.dlp = self.extract_technical_value(section, self.technical_patterns['dlp'])
            dose.size_specific_dose = self.extract_technical_value(section,
                                                                   self.technical_patterns['specific_dose']) or None
            dose.ctdivol_alert_value = self.extract_technical_value(section,
                                                                    self.technical_patterns['alert_value']) or None
            acquisition.ct_dose = dose

            acquisitions.append(acquisition)

        return acquisitions

    def extract_from_pdf(self, pdf_path: str, debug_mode: bool = False) -> CTScanReportMinimal:
        """Extrai informações de um arquivo PDF - Versão Minimal"""
        report = CTScanReportMinimal()
        full_text = ""

        doc = pymupdf.open(pdf_path)
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()

        if debug_mode:
            print(f"\n{'=' * 60}")
            print("VERSÃO AGNÓSTICA - EXTRAINDO APENAS INFORMAÇÕES ESSENCIAIS")
            print(f"{'=' * 60}")

        # Extrai informações do hospital
        report.hospital, report.report_date = self.extract_hospital_info(full_text)

        # Extrai TODOS os dados essenciais (incluindo o novo nome)
        report.essential.patient_id = self.extract_essential_value(full_text, self.essential_patterns['patient_id'])
        report.essential.patient_name = self.extract_patient_name(full_text)
        report.essential.study_id = self.extract_essential_value(full_text, self.essential_patterns['study_id'])
        report.essential.accession_number = self.extract_essential_value(full_text,
                                                                         self.essential_patterns['accession_number'])
        report.essential.study_date = self.extract_study_date_clean(full_text)
        report.essential.birth_date = self.extract_essential_value(full_text, self.essential_patterns['birth_date'])
        report.essential.sex = self.extract_essential_value(full_text, self.essential_patterns['sex'])

        if debug_mode:
            print("DADOS ESSENCIAIS EXTRAÍDOS:")
            print(f"  Patient ID: '{report.essential.patient_id}'")
            print(f"  Patient Name: '{report.essential.patient_name}'")
            print(f"  Study ID: '{report.essential.study_id}'")
            print(f"  Accession Number: '{report.essential.accession_number}'")
            print(f"  Study Date: '{report.essential.study_date}'")
            print(f"  Birth Date: '{report.essential.birth_date}'")
            print(f"  Sex: '{report.essential.sex}'")
            print(f"{'=' * 60}\n")

        # Extrai dados técnicos
        report.device.observer_name = self.extract_technical_value(full_text, self.technical_patterns['device_name'])
        report.device.manufacturer = self.extract_technical_value(full_text, self.technical_patterns['manufacturer'])
        report.device.model_name = self.extract_technical_value(full_text, self.technical_patterns['model_name'])
        report.device.serial_number = self.extract_technical_value(full_text, self.technical_patterns['serial_number'])
        report.device.physical_location = self.extract_physical_location_multiline(full_text)

        # Extrai informações de irradiação
        report.irradiation.start_time = self.extract_technical_value(full_text,
                                                                     self.technical_patterns['start_irradiation'])
        report.irradiation.end_time = self.extract_technical_value(full_text,
                                                                   self.technical_patterns['end_irradiation'])
        report.irradiation.total_events = self.extract_technical_value(full_text,
                                                                       self.technical_patterns['total_events'])
        report.irradiation.total_dlp = self.extract_technical_value(full_text, self.technical_patterns['total_dlp'])

        # Extrai aquisições CT
        report.acquisitions = self.extract_ct_acquisitions(full_text)

        return report


def process_pdf_folder(folder_path: str = "ct_reports", json_folder: str = "ct_reports_json",
                       debug_mode: bool = False) -> List[Dict]:
    """Processa todos os arquivos PDF em uma pasta específica"""

    # Cria a pasta se não existir
    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
            print(f"✓ Pasta '{folder_path}' criada com sucesso!")
        except Exception as e:
            print(f"✗ Erro ao criar pasta '{folder_path}': {str(e)}")
            return []

    # Busca todos os arquivos PDF na pasta (compatível com Windows, Mac e Linux)
    pdf_pattern = os.path.join(folder_path, "*.pdf")
    pdf_files = glob.glob(pdf_pattern)

    if not pdf_files:
        print(f"ℹ️ Nenhum arquivo PDF encontrado na pasta '{folder_path}'.")
        return []

    print(f"🔍 Encontrados {len(pdf_files)} arquivos PDF para processar.")

    # Processa os PDFs encontrados
    extractor = CTReportExtractorMinimal()
    reports = []

    for pdf_file in pdf_files:
        try:
            if debug_mode:
                print(f"\n{'=' * 60}")
                print(f"PROCESSANDO: {os.path.basename(pdf_file)}")
                print(f"{'=' * 60}")

            report = extractor.extract_from_pdf(pdf_file, debug_mode=debug_mode)
            report_dict = asdict(report)
            reports.append(report_dict)

            # Salva o relatório individual usando o Patient ID
            patient_id = report.essential.patient_id
            if patient_id:
                output_file = f"ct_report_{patient_id}.json"
                save_to_json([report_dict], output_file, json_folder)
                print(f"✓ Processado e salvo: {os.path.basename(pdf_file)} → {os.path.join(json_folder, output_file)}")
            else:
                print(f"✓ Processado: {os.path.basename(pdf_file)} (sem Patient ID)")

        except Exception as e:
            print(f"✗ Erro ao processar {os.path.basename(pdf_file)}: {str(e)}")

    return reports


def save_to_json(reports: List[Dict], output_file: str, json_folder: str = "ct_reports_json"):
    """Salva os relatórios em um arquivo JSON"""
    # Cria a pasta JSON se não existir
    if not os.path.exists(json_folder):
        try:
            os.makedirs(json_folder)
            print(f"✓ Pasta '{json_folder}' criada com sucesso!")
        except Exception as e:
            print(f"⚠️ Erro ao criar pasta '{json_folder}': {str(e)}")
            json_folder = ""

    # Caminho completo para o arquivo
    output_path = os.path.join(json_folder, output_file) if json_folder else output_file

    # Salva o JSON
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(reports, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"⚠️ Erro ao salvar {output_path}: {str(e)}")
        return False


if __name__ == "__main__":
    import argparse

    # Configuração dos argumentos de linha de comando
    parser = argparse.ArgumentParser(description='Extrator de informações de relatórios de dose de CT')
    parser.add_argument('--folder', type=str, default='ct_reports',
                        help='Pasta contendo os arquivos PDF (padrão: ct_reports)')
    parser.add_argument('--output-folder', type=str, default='ct_reports_json',
                        help='Pasta para salvar os arquivos JSON (padrão: ct_reports_json)')
    parser.add_argument('--debug', action='store_true',
                        help='Ativa o modo debug com informações detalhadas')
    parser.add_argument('--output', type=str, default='ct_reports_all.json',
                        help='Nome do arquivo JSON de saída com todos os relatórios (padrão: ct_reports_all.json)')

    args = parser.parse_args()

    print(f"\n{'=' * 80}")
    print("CTDoseExtractor - Extrator de Relatórios de Dose de CT")
    print(f"{'=' * 80}")
    print(f"Pasta de entrada (PDFs): {args.folder}")
    print(f"Pasta de saída (JSONs): {args.output_folder}")
    print(f"Modo debug: {'Ativado' if args.debug else 'Desativado'}")
    print(f"Arquivo de saída completo: {os.path.join(args.output_folder, args.output)}")
    print(f"{'=' * 80}\n")

    # Processa a pasta de PDFs
    reports_array = process_pdf_folder(args.folder, args.output_folder, debug_mode=args.debug)

    if not reports_array:
        print("⚠️ Nenhum relatório processado. Verifique a pasta com os arquivos PDF.")
        exit(0)

    # Salva todos os resultados em um único JSON
    save_to_json(reports_array, args.output, args.output_folder)
    print(f"\n✅ Processamento concluído!")
    print(f"  • Total de relatórios processados: {len(reports_array)}")
    print(f"  • Arquivo com todos os relatórios: {os.path.join(args.output_folder, args.output)}")
    print(f"  • Arquivos individuais: {os.path.join(args.output_folder, 'ct_report_[PATIENT_ID].json')}")

    # Exibe resumo do primeiro relatório como exemplo
    if reports_array:
        first_report = reports_array[0]
        print(f"\n📋 EXEMPLO DO PRIMEIRO RELATÓRIO PROCESSADO:")
        print(f"  • Hospital: {first_report['hospital']}")
        patient_id = first_report['essential']['patient_id']
        patient_name = first_report['essential']['patient_name']
        study_id = first_report['essential']['study_id']
        accession = first_report['essential']['accession_number']
        study_date = first_report['essential']['study_date']
        print(f"  • Patient ID: {patient_id}")
        print(f"  • Patient Name: {patient_name}")
        print(f"  • Study ID: {study_id}")
        print(f"  • Accession Number: {accession}")
        print(f"  • Study Date: {study_date}")
        print(f"  • Birth Date: {first_report['essential']['birth_date']}")
        print(f"  • Sex: {first_report['essential']['sex']}")
        print(f"  • Total de aquisições: {len(first_report['acquisitions'])}")
        print(f"  • Arquivo individual: {os.path.join(args.output_folder, f'ct_report_{patient_id}.json')}")

    print(f"\n💡 Para mais detalhes, use --debug\n")
