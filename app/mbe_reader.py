"""Read native EXPA/CHNK MBE sheets without a GUI dependency."""
import struct

COLUMN_TYPES_BY_CODE = {
    0x2: {'name': 'int',      'code': 0x2, 'size': 4, 'format': '<i'},
    0x3: {'name': 'short',    'code': 0x3, 'size': 2, 'format': '<h'},
    0x4: {'name': 'byte',     'code': 0x4, 'size': 1, 'format': '<b'},
    0x5: {'name': 'float',    'code': 0x5, 'size': 4, 'format': '<f'},
    0x6: {'name': 'string3',  'code': 0x6, 'size': 8, 'format': '<q'},
    0x7: {'name': 'string',   'code': 0x7, 'size': 8, 'format': '<q'},
    0x8: {'name': 'string2',  'code': 0x8, 'size': 8, 'format': '<q'},
    0x9: {'name': 'bool',     'code': 0x9, 'size': 4, 'format': '<i'},
    0xA: {'name': 'empty',    'code': 0xA, 'size': 0, 'format': '<i'},
}


def _read_padded_string(f, size):
    if size <= 0:
        return ""
    return f.read(size).decode('utf-8', errors='ignore').rstrip('\x00')


def read_mbe(f):
    """Read all native sheets, columns and values from a seekable binary stream."""
    try:
        magic = f.read(4)
        if magic != b'EXPA':
            raise ValueError(f"Invalid MBE file format. Expected magic number 'EXPA', but found: {magic!r}. File may be corrupted or not an MBE file.")

        num_expa_regions_bytes = f.read(4)
        if len(num_expa_regions_bytes) < 4:
            raise ValueError("File is too short. Could not read number of EXPA regions.")
        num_expa_regions, = struct.unpack('<i', num_expa_regions_bytes)

        if num_expa_regions < 0 or num_expa_regions > 1000:
            raise ValueError(f"Invalid number of EXPA regions: {num_expa_regions}. File may be corrupted.")

    except struct.error as e:
        raise ValueError(f"Error reading MBE file header: {e}. File may be corrupted or truncated.")

    all_sheets, string_map = [], {}
    offset = 8

    for sheet_idx in range(num_expa_regions):
        try:
            # Align to 8-byte boundary
            offset = (offset + 7) & ~7
            f.seek(offset)

            sheet_name_size_bytes = f.read(4)
            if len(sheet_name_size_bytes) < 4:
                raise ValueError(f"Error reading sheet {sheet_idx + 1} header: file truncated at offset {offset}")
            sheet_name_size, = struct.unpack('<i', sheet_name_size_bytes)

            if sheet_name_size < 0 or sheet_name_size > 1000:
                raise ValueError(f"Invalid sheet name size {sheet_name_size} for sheet {sheet_idx + 1} at offset {offset}")

            sheet_name = _read_padded_string(f, sheet_name_size)

            num_cols_bytes = f.read(4)
            if len(num_cols_bytes) < 4:
                raise ValueError(f"Error reading column count for sheet '{sheet_name}' (sheet {sheet_idx + 1}): file truncated")
            num_cols, = struct.unpack('<i', num_cols_bytes)

            if num_cols < 0 or num_cols > 1000:
                raise ValueError(f"Invalid column count {num_cols} for sheet '{sheet_name}' (sheet {sheet_idx + 1})")

            col_codes_bytes = f.read(4 * num_cols)
            if len(col_codes_bytes) < 4 * num_cols:
                raise ValueError(f"Error reading column codes for sheet '{sheet_name}' (sheet {sheet_idx + 1}): file truncated")
            col_codes = struct.unpack(f'<{num_cols}i', col_codes_bytes)

            try:
                columns = [COLUMN_TYPES_BY_CODE[code] for code in col_codes]
            except KeyError as e:
                invalid_code = e.args[0] if e.args else "unknown"
                raise ValueError(f"Unknown column type code {invalid_code} in sheet '{sheet_name}' (sheet {sheet_idx + 1}). Column codes: {col_codes}")

            area_size_bytes = f.read(8)
            if len(area_size_bytes) < 8:
                raise ValueError(f"Error reading area size for sheet '{sheet_name}' (sheet {sheet_idx + 1}): file truncated")
            area_size, num_areas = struct.unpack('<ii', area_size_bytes)

            if area_size < 0 or area_size > 100000:
                raise ValueError(f"Invalid area size {area_size} for sheet '{sheet_name}' (sheet {sheet_idx + 1})")
            if num_areas < 0 or num_areas > 100000:
                raise ValueError(f"Invalid number of areas {num_areas} for sheet '{sheet_name}' (sheet {sheet_idx + 1})")

        except struct.error as e:
            raise ValueError(f"Error parsing sheet {sheet_idx + 1} header: {e}. File may be corrupted.")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Unexpected error parsing sheet {sheet_idx + 1}: {e}")

        # Calculate total header size and align
        header_size = 4 + sheet_name_size + 4 + 4 * num_cols + 8
        header_size = (header_size + 7) & ~7
        offset += header_size

        rows = []
        for row_idx in range(num_areas):
            try:
                # Align to 8-byte boundary for each row
                offset = (offset + 7) & ~7
                f.seek(offset)

                row_start_offset = f.tell()
                row_bytes = f.read(area_size)

                if len(row_bytes) < area_size:
                    raise ValueError(f"Error reading row {row_idx + 1} in sheet '{sheet_name}' (sheet {sheet_idx + 1}): expected {area_size} bytes but got {len(row_bytes)}. File truncated at offset {offset}")

                parsed_row, offset_in_row = [], 0
                bit_offset = 0
                bool_value = 0  # Separate variable for bool bit extraction

                for col_idx, col in enumerate(columns):
                    try:
                        if col['name'] == 'bool':
                            if bit_offset == 0:
                                # Align to 4-byte boundary for bool
                                offset_in_row = (offset_in_row + 3) & ~3
                                if offset_in_row + 4 > len(row_bytes):
                                    raise ValueError(f"Row {row_idx + 1}, column {col_idx + 1} ({col['name']}): offset {offset_in_row} + 4 exceeds row size {len(row_bytes)}")
                                val_bytes = row_bytes[offset_in_row:offset_in_row + 4]
                                bool_value, = struct.unpack('<i', val_bytes)
                                offset_in_row += 4
                            # Extract bit from the 32-bit value
                            bit_val = (bool_value >> bit_offset) & 1
                            parsed_row.append(bit_val)
                            bit_offset += 1
                            if bit_offset >= 32:
                                bit_offset = 0
                        elif col['name'] == 'empty':
                            parsed_row.append('')
                        elif 'string' in col['name']:
                            # Align to 8-byte boundary for strings
                            offset_in_row = (offset_in_row + 7) & ~7
                            if offset_in_row + 8 > len(row_bytes):
                                raise ValueError(f"Row {row_idx + 1}, column {col_idx + 1} ({col['name']}): offset {offset_in_row} + 8 exceeds row size {len(row_bytes)}")
                            string_map[row_start_offset + offset_in_row] = (sheet_idx, row_idx, col_idx)
                            parsed_row.append('')
                            offset_in_row += 8
                        else:
                            # Handle other types with proper alignment
                            if col['name'] == 'short':
                                offset_in_row = (offset_in_row + 1) & ~1
                            elif col['name'] in ['int', 'float']:
                                offset_in_row = (offset_in_row + 3) & ~3

                            if offset_in_row + col['size'] > len(row_bytes):
                                raise ValueError(f"Row {row_idx + 1}, column {col_idx + 1} ({col['name']}): offset {offset_in_row} + {col['size']} exceeds row size {len(row_bytes)}")
                            val_bytes = row_bytes[offset_in_row:offset_in_row + col['size']]
                            val, = struct.unpack(col['format'], val_bytes)
                            parsed_row.append(val)
                            offset_in_row += col['size']
                    except struct.error as e:
                        raise ValueError(f"Error parsing row {row_idx + 1}, column {col_idx + 1} ({col['name']}) in sheet '{sheet_name}': {e}")
                    except Exception as e:
                        if isinstance(e, ValueError):
                            raise
                        raise ValueError(f"Unexpected error parsing row {row_idx + 1}, column {col_idx + 1} in sheet '{sheet_name}': {e}")

                # Handle remaining bool bits
                if bit_offset > 0:
                    offset_in_row += 4

                rows.append(parsed_row)
                offset += area_size + ((area_size + 7) & ~7) - area_size
            except Exception as e:
                if isinstance(e, ValueError):
                    raise
                raise ValueError(f"Error parsing row {row_idx + 1} in sheet '{sheet_name}' (sheet {sheet_idx + 1}): {e}")

        all_sheets.append({'name': sheet_name, 'columns': columns, 'rows': rows})

    # Align to 8-byte boundary before CHNK section
    offset = (offset + 7) & ~7
    f.seek(offset)

    chnk_magic = f.read(4)
    if chnk_magic == b'CHNK':
        try:
            num_strings_bytes = f.read(4)
            if len(num_strings_bytes) < 4:
                raise ValueError("Error reading CHNK section: file truncated while reading string count")
            num_strings, = struct.unpack('<i', num_strings_bytes)

            if num_strings < 0 or num_strings > 100000:
                raise ValueError(f"Invalid number of strings in CHNK section: {num_strings}")

            for str_idx in range(num_strings):
                try:
                    offset_size_bytes = f.read(8)
                    if len(offset_size_bytes) < 8:
                        raise ValueError(f"Error reading string {str_idx + 1} of {num_strings} in CHNK section: file truncated")
                    offset, size = struct.unpack('<ii', offset_size_bytes)

                    if size < 0 or size > 10000:
                        raise ValueError(f"Invalid string size {size} for string {str_idx + 1} in CHNK section")

                    text = _read_padded_string(f, size)
                    if offset in string_map:
                        s_idx, r_idx, c_idx = string_map[offset]
                        all_sheets[s_idx]['rows'][r_idx][c_idx] = text
                except struct.error as e:
                    raise ValueError(f"Error reading string {str_idx + 1} in CHNK section: {e}")
                except Exception as e:
                    if isinstance(e, ValueError):
                        raise
                    raise ValueError(f"Unexpected error reading string {str_idx + 1} in CHNK section: {e}")
        except struct.error as e:
            raise ValueError(f"Error parsing CHNK section: {e}. File may be corrupted.")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Unexpected error in CHNK section: {e}")

    # Convert empty string fields to '""' for display
    for sheet in all_sheets:
        for row in sheet['rows']:
            for c_idx, col in enumerate(sheet['columns']):
                if 'string' in col['name'] and row[c_idx] == '':
                    row[c_idx] = '""'

    return all_sheets
