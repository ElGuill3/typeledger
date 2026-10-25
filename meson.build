project('typeledger',
  version: '0.1.0',
  meson_version: '>= 1.0.0',
)

i18n = import('i18n')
python = import('python').find_installation('python3')

app_id = 'io.github.elguill3.TypeLedger'
localedir = get_option('prefix') / get_option('localedir')

subdir('typeledger')
subdir('data')
subdir('bin')
subdir('po')
