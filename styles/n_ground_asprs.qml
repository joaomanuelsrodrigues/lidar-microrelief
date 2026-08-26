<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="AllStyleCategories">
  <pipe>
    <rasterrenderer type="singlebandpseudocolor" band="1" opacity="1" alphaBand="-1" classificationMin="0" classificationMax="1">
      <minMaxOrigin><limits>MinMax</limits><extent>UpdatedCanvas</extent><statAccuracy>Exact</statAccuracy></minMaxOrigin>
      <rastershader>
        <colorrampshader colorRampType="INTERPOLATED" classificationMode="1" clip="0" minimumValue="0" maximumValue="1">
        <colorramp type="gradient" name="[source]">
          <Option type="Map">
            <Option name="color1" type="QString" value="68,1,84,255"/>
            <Option name="color2" type="QString" value="253,231,36,255"/>
            <Option name="discrete" type="QString" value="0"/>
            <Option name="rampType" type="QString" value="gradient"/>
            <Option name="stops" type="QString" value="0.125;71,44,123,255:0.25;58,82,139,255:0.375;44,114,142,255:0.5;32,144,140,255:0.625;40,174,127,255:0.75;94,201,97,255:0.875;173,220,48,255"/>
          </Option>
        </colorramp>
          <item value="0" color="#440154" alpha="255" label="0%"/>
          <item value="0.125" color="#472c7b" alpha="255" label="12%"/>
          <item value="0.25" color="#3a528b" alpha="255" label="25%"/>
          <item value="0.375" color="#2c728e" alpha="255" label="38%"/>
          <item value="0.5" color="#20908c" alpha="255" label="50%"/>
          <item value="0.625" color="#28ae7f" alpha="255" label="62%"/>
          <item value="0.75" color="#5ec961" alpha="255" label="75%"/>
          <item value="0.875" color="#addc30" alpha="255" label="88%"/>
          <item value="1" color="#fde724" alpha="255" label="100%"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation saturation="0" grayscaleMode="0"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
