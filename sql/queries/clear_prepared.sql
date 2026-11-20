DELETE FROM OML_BASIC_PREPARED
 WHERE (:variant = 'ALL' OR PREP_MODE = :variant)
   AND (:source_kind = 'ALL' OR SOURCE_KIND = :source_kind)
