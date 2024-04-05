import os
import xml.etree.ElementTree as ET
import argparse

def extract_values(data_set):
    values = {}
    for element in data_set.findall('.//element'):
        tag = element.get('tag')
        value = element.text.strip() if element.text else ""
        if tag == '0010,0020':
            values['PatientID'] = value
        elif tag == '0008,0020':
            values['StudyDate'] = value
        elif tag == '0008,1030':
            values['StudyDescription'] = value
        elif tag == '0008,0050':
            values['AccessionNumber'] = value
        elif tag == '0020,0011':
            values['SeriesNumber'] = value
        elif tag == '0008,103e':
            values['SeriesDescription'] = value
        elif tag == '0020,000e':
            values['SeriesInstanceUID'] = value
    return values

def process_folder(folder_path):
    output_filename = os.path.basename(folder_path) + "_list.tsv"
    output_path = os.path.join(folder_path, output_filename)

    headers = ['PatientID', 'StudyDate', 'StudyDescription', 'AccessionNumber', 'SeriesNumber', 'SeriesDescription', 'SeriesInstanceUID']

    with open(output_path, 'w') as tsv_file:
        tsv_file.write('\t'.join(headers) + '\n')

        for filename in os.listdir(folder_path):
            if filename.endswith('.xml'):
                xml_path = os.path.join(folder_path, filename)
                tree = ET.parse(xml_path)
                root = tree.getroot()

                for data_set in root.findall('.//data-set'):
                    values = extract_values(data_set)
                    row = [values.get(header, '') for header in headers]
                    tsv_file.write('\t'.join(row) + '\n')

def main():
    parser = argparse.ArgumentParser(description='Process XML files in a directory to extract medical imaging data.')
    parser.add_argument('path', type=str, help='The path to the directory containing XML files.')

    args = parser.parse_args()
    process_folder(args.path)

if __name__ == '__main__':
    main()
