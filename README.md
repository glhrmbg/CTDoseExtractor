# CTDoseExtractor

Um extrator robusto de informações de relatórios de dose de radiação de tomografia computadorizada (CT) em formato PDF, com exportação para Excel.

## 📋 Visão Geral

O CTDoseExtractor é uma ferramenta agnóstica desenvolvida para extrair automaticamente informações estruturadas de relatórios de dose de radiação X-Ray gerados por equipamentos de tomografia computadorizada. O projeto prioriza a extração confiável de **identificadores únicos** essenciais e dados técnicos das aquisições CT.

## 🎯 Estratégia de Extração

Esta ferramenta usa uma abordagem **agnóstica** que foca nos dados mais importantes e confiáveis:

### ✅ Dados Prioritários (Alta Confiabilidade)
- **Patient ID** - Identificação única do paciente
- **Birth Date** - Data de nascimento
- **Sex** - Sexo do paciente
- **Study ID** - Identificação do estudo
- **Accession Number** - Número de acesso único
- **Study Date** - Data do exame
- **Dados Técnicos Completos** - Parâmetros de aquisição, doses, equipamento

### ℹ️ Por que essa abordagem?
Os PDFs de relatórios CT frequentemente apresentam formatação em múltiplas colunas que pode corromper a extração de campos como nome do paciente. Nossa estratégia prioriza os **identificadores únicos** que permitem localizar qualquer exame no sistema hospitalar, garantindo alta confiabilidade na extração dos dados mais críticos.

## 🚀 Instalação e Uso

### Pré-requisitos
```bash
pip install pdfplumber openpyxl
```

### Uso Básico (Linha de Comando)

1. Coloque seus PDFs na pasta `ct_reports` no mesmo diretório do script
2. Execute os scripts:

```bash
# Extrair dados dos PDFs para JSON
python CTDoseExtractor.py

# Converter JSONs para Excel
python CTDoseExcel.py
```

### Opções do CTDoseExtractor

```bash
# Usar pasta diferente para PDFs
python CTDoseExtractor.py --folder minha_pasta_pdfs

# Especificar pasta de saída para JSONs
python CTDoseExtractor.py --output-folder resultados_json

# Ativar modo debug (mostra detalhes da extração)
python CTDoseExtractor.py --debug

# Especificar nome do arquivo de saída coletivo
python CTDoseExtractor.py --output relatorios_completos.json

# Todas as opções juntas
python CTDoseExtractor.py --folder pdfs --output-folder jsons --output todos.json --debug
```

### Opções do CTDoseExcel

```bash
# Especificar pasta com JSONs
python CTDoseExcel.py --input-folder minha_pasta_json

# Especificar nome do arquivo Excel de saída
python CTDoseExcel.py --output relatorio_dose_ct.xlsx

# Ambas as opções
python CTDoseExcel.py --input-folder dados_json --output relatorio.xlsx
```

### Uso como Biblioteca Python

```python
from CTDoseExtractor import CTReportExtractorMinimal, process_pdf_folder, save_to_json

# Processar uma pasta inteira de PDFs
reports = process_pdf_folder("minha_pasta_com_pdfs", debug_mode=False)

# Processar um único PDF
extractor = CTReportExtractorMinimal()
report = extractor.extract_from_pdf("relatorio_ct.pdf")

# Acessar os dados essenciais
patient_id = report.essential.patient_id
study_id = report.essential.study_id
```

## 📊 Estrutura dos Dados Extraídos

### JSON

```json
{
  "hospital": "Hospital Universitario ...",
  "report_date": "May 5, 2025, 1:21:31 PM",
  "essential": {
    "patient_id": "05074687",
    "study_id": "009211", 
    "accession_number": "342865",
    "study_date": "May 5, 2025, 1:20:41 PM",
    "birth_date": "Jul 1, 1997",
    "sex": "Female"
  },
  "device": {
    "observer_name": "CT",
    "manufacturer": "Philips",
    "model_name": "Incisive CT",
    "serial_number": "541024",
    "physical_location": "Hospital Universitario..."
  },
  "irradiation": {
    "start_time": "Mon May 05 13:20:49 BRT 2025",
    "end_time": "Mon May 05 13:21:27 BRT 2025",
    "total_events": "2.0 events",
    "total_dlp": "445.02 mGy.cm"
  },
  "acquisitions": [
    {
      "protocol": "Seios da Face",
      "target_region": "Facial bones",
      "acquisition_params": {
        "exposure_time": "8.4423 s",
        "scanning_length": "225.6 mm",
        "nominal_single_collimation": "0.63 mm",
        "nominal_total_collimation": "40.0 mm",
        "num_xray_sources": "1.0 X-Ray sources",
        "pitch_factor": "0.5 ratio"
      },
      "xray_source_params": {
        "identification": "A",
        "kvp": "120.0 kV",
        "max_tube_current": "667.0 mA",
        "tube_current": "93.0 mA",
        "exposure_time_per_rotation": "0.75 s"
      },
      "ct_dose": {
        "mean_ctdivol": "19.62 mGy",
        "phantom_type": "IEC Head Dosimetry Phantom",
        "dlp": "442.55 mGy.cm",
        "size_specific_dose": "16.72 mGy",
        "ctdivol_alert_value": "1000.0 mGy"
      }
    }
  ]
}
```

### Excel

O arquivo Excel gerado pelo `CTDoseExcel.py` inclui as seguintes colunas:
- ID do paciente
- Sexo
- Data de nascimento
- Idade (calculada automaticamente)
- Pesquisa de interesse (protocolo de aquisição)
- Data do exame
- Descrição da série (comentário da aquisição)
- Scan mode
- mAs
- kV
- CTDIvol
- DLP
- DLP total
- Phantom type
- SSDE
- Avg scan size

## 🔧 Características Técnicas

### Robustez na Extração
- **Múltiplos padrões regex** por campo essencial
- **Preservação de unidades** nos valores técnicos  
- **Tratamento de formatações inconsistentes**
- **Detecção automática de múltiplas aquisições CT**

### Tratamento de Problemas Comuns
- PDFs com layout de múltiplas colunas
- Espaçamentos inconsistentes  
- Quebras de linha inesperadas
- Formatações variadas de campos
- Valores nulos (substituídos por "-" na exportação Excel)

## 📊 Exportação para Excel

O script `CTDoseExcel.py` permite:

- Gerar uma planilha formatada com todos os dados importantes
- Calcular a idade automaticamente a partir da data de nascimento
- Tratar valores nulos adequadamente (substituindo por "-")
- Manter todas as unidades originais

## 📂 Estrutura de Arquivos

```
CTDoseExtractor/
├── CTDoseExtractor.py       # Script de extração PDF → JSON
├── CTDoseExcel.py           # Script de conversão JSON → Excel
├── README.md                # Este arquivo
├── requirements.txt         # Dependências (pdfplumber, openpyxl)
├── ct_reports/              # Pasta para PDFs (criada automaticamente)
│   ├── relatorio1.pdf       # Seus arquivos PDF...
│   ├── relatorio2.pdf
│   └── ...
├── ct_reports_json/         # Pasta para JSONs gerados (criada automaticamente)
│   ├── ct_reports_all.json  # JSON com TODOS os relatórios
│   ├── ct_report_05074687.json  # JSON individual (Patient ID 05074687)
│   └── ct_report_12345678.json  # JSON individual (Patient ID 12345678)
└── ct_dose_report.xlsx      # Planilha Excel com todos os dados (gerada pelo CTDoseExcel.py)
```

## 🎓 Contexto Acadêmico

Este projeto foi desenvolvido como ferramenta de apoio para pesquisa universitária em **análise de doses de radiação** em exames de tomografia computadorizada. O foco em identificadores únicos permite integração eficiente com sistemas de informação hospitalares existentes.

---

⚕️ **Importante**: Esta ferramenta foi desenvolvida para fins de pesquisa acadêmica. Sempre verifique a precisão dos dados extraídos antes de usar em análises críticas.