desktop_file = i18n.merge_file(
  input: configure_file(
    input: 'io.github.elguill3.TypeLedger.desktop.in',
    output: 'io.github.elguill3.TypeLedger.desktop.in',
    copy: true,
  ),
  output: 'io.github.elguill3.TypeLedger.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications',
)

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: [desktop_file])
endif
