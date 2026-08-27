<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="AllStyleCategories">
  <pipe>
    <rasterrenderer type="singlebandpseudocolor" band="1" opacity="1" alphaBand="-1" classificationMin="0" classificationMax="1">
      <minMaxOrigin><limits>MinMax</limits><extent>UpdatedCanvas</extent><statAccuracy>Exact</statAccuracy></minMaxOrigin>
      <rastershader>
        <colorrampshader colorRampType="INTERPOLATED" classificationMode="1" clip="0" minimumValue="0" maximumValue="1">
        <colorramp type="gradient" name="[source]">
          <Option type="Map">
            <Option name="color1" type="QString" value="51,51,153,255"/>
            <Option name="color2" type="QString" value="255,255,255,255"/>
            <Option name="discrete" type="QString" value="0"/>
            <Option name="rampType" type="QString" value="gradient"/>
            <Option name="stops" type="QString" value="0.125;8,136,238,255:0.25;1,204,102,255:0.375;129,229,127,255:0.5;254,253,152,255:0.625;190,171,117,255:0.75;129,93,86,255:0.875;193,175,171,255"/>
          </Option>
        </colorramp>
          <item value="0" color="#333399" alpha="255" label="0%"/>
          <item value="0.125" color="#0888ee" alpha="255" label="12%"/>
          <item value="0.25" color="#01cc66" alpha="255" label="25%"/>
          <item value="0.375" color="#81e57f" alpha="255" label="38%"/>
          <item value="0.5" color="#fefd98" alpha="255" label="50%"/>
          <item value="0.625" color="#beab75" alpha="255" label="62%"/>
          <item value="0.75" color="#815d56" alpha="255" label="75%"/>
          <item value="0.875" color="#c1afab" alpha="255" label="88%"/>
          <item value="1" color="#ffffff" alpha="255" label="100%"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation saturation="0" grayscaleMode="0"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
