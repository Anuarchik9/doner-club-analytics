import sales_channel


def install_speed_patch(app):
    if getattr(app, "_doner_speed_patch_installed", False):
        return
    app._doner_speed_patch_installed = True

    original_filter_ui_script = sales_channel._filter_ui_script

    def faster_filter_ui_script():
        script = original_filter_ui_script()
        old = """if(channel==='all'){
      await originalLoad.call(go);
      const mix=await loadMix(point,a,b);"""
        new = """if(channel==='all'){
      const mixPromise=loadMix(point,a,b);
      await originalLoad.call(go);
      const mix=await mixPromise;"""
        return script.replace(old, new)

    sales_channel._filter_ui_script = faster_filter_ui_script
