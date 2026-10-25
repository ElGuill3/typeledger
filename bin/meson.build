conf = configuration_data()
conf.set('PYTHON', python.full_path())
conf.set('PYTHONDIR', python.get_install_dir())
conf.set('LOCALEDIR', localedir)

configure_file(
  input: 'typeledger.in',
  output: 'typeledger',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)
