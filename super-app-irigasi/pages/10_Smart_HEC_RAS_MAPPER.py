import os
import logging
import warnings
from typing import Optional, List, Dict, Any, Union

# Pustaka Geospatial Utama
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, MultiLineString
from shapely.ops import validate
import shapely.wkt

# Pustaka Khusus CAD
import ezdxf
from ezdxf.addons import drawing
from ezdxf import path

# Pustaka Database
from sqlalchemy import create_engine
from geoalchemy2 import Geometry, WKTElement

# Konfigurasi Logging agar output informatif
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mengabaikan warning spesifik dari pyogrio/runtime untuk kebersihan output
warnings.filterwarnings('ignore')

class GeoIngestor:
    """
    Kelas utama untuk menangani pembacaan file spasial (SHP, DXF, GJSON)
    dan mengunggahnya ke database PostGIS.
    """

    def __init__(self, db_connection_string: str):
        """
        Inisialisasi koneksi ke database GIS.
        
        Args:
            db_connection_string (str): Connection string SQLAlchemy.
            Contoh: 'postgresql+psycopg2://user:password@host:5432/dbname'
        """
        try:
            self.engine = create_engine(db_connection_string)
            # Tes koneksi
            with self.engine.connect() as connection:
                logger.info("Koneksi ke PostGIS berhasil dibangun.")
        except Exception as e:
            logger.error(f"Gagal terhubung ke database: {e}")
            raise e

    def read_file(self, file_path: str, source_crs: Optional[str] = None) -> gpd.GeoDataFrame:
        """
        Fungsi pintar yang mendeteksi ekstensi file dan memanggil pembaca yang sesuai.
        
        Args:
            file_path (str): Lokasi file input.
            source_crs (str, optional): Kode CRS (misal 'EPSG:4326') jika file tidak memiliki referensi (wajib untuk DXF).
            
        Returns:
            gpd.GeoDataFrame: Dataframe spasial yang telah dinormalisasi.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        logger.info(f"Mendeteksi format file: {ext}")

        if ext == '.shp':
            return self._read_shapefile(file_path, source_crs)
        elif ext in ['.geojson', '.json', '.gjson']:
            return self._read_geojson(file_path, source_crs)
        elif ext == '.dxf':
            return self._read_dxf(file_path, source_crs)
        else:
            raise ValueError(f"Format file {ext} tidak didukung. Gunakan.shp,.dxf, atau.geojson")

    def _read_shapefile(self, path: str, crs_override: Optional[str]) -> gpd.GeoDataFrame:
        """Membaca Shapefile menggunakan engine pyogrio untuk performa maksimal."""
        try:
            # Menggunakan engine="pyogrio" 
            gdf = gpd.read_file(path, engine="pyogrio")
            
            # Validasi CRS
            if gdf.crs is None:
                if crs_override:
                    logger.warning(f"Shapefile tidak memiliki CRS. Mengatur manual ke {crs_override}")
                    gdf.set_crs(crs_override, inplace=True)
                else:
                    logger.warning("PERINGATAN: Shapefile tidak memiliki CRS dan tidak ada override. Data mungkin tidak akurat secara spasial.")
            
            return gdf
        except Exception as e:
            logger.error(f"Error membaca Shapefile: {e}")
            raise

    def _read_geojson(self, path: str, crs_override: Optional[str]) -> gpd.GeoDataFrame:
        """Membaca GeoJSON."""
        try:
            # GeoPandas otomatis menangani GeoJSON
            gdf = gpd.read_file(path, engine="pyogrio")
            
            # GeoJSON standar biasanya EPSG:4326. 
            if crs_override and gdf.crs is None:
                gdf.set_crs(crs_override, inplace=True)
                
            return gdf
        except Exception as e:
            logger.error(f"Error membaca GeoJSON: {e}")
            raise

    def _read_dxf(self, filepath: str, crs: str) -> gpd.GeoDataFrame:
        """
        Membaca DXF menggunakan ezdxf untuk presisi geometri.
        Mengonversi entitas CAD (Spline, Arc, Hatch) menjadi Simple Features (LineString, Polygon).
        """
        if not crs:
            logger.warning("Membaca DXF tanpa CRS. Data akan berada dalam koordinat kartesius lokal (Engineering CRS).")

        try:
            doc = ezdxf.readfile(filepath)
            msp = doc.modelspace()
            
            geometries =
            properties =

            logger.info("Memulai konversi entitas DXF ke geometri GIS...")

            # Iterasi entitas di Model Space
            for entity in msp:
                dxftype = entity.dxftype()
                geom = None
                attribs = {'layer': entity.dxf.layer, 'type': dxftype}

                try:
                    # 1. Point
                    if dxftype == 'POINT':
                        loc = entity.dxf.location
                        geom = Point(loc.x, loc.y)

                    # 2. Line
                    elif dxftype == 'LINE':
                        start = entity.dxf.start
                        end = entity.dxf.end
                        geom = LineString([(start.x, start.y), (end.x, end.y)])

                    # 3. Polyline & LWPolyline
                    elif dxftype in:
                        # Menggunakan ezdxf.path untuk menangani polyline dengan bulge (lengkungan)
                        p = path.make_path(entity)
                        # Flattening mengubah kurva menjadi segmen garis (teselasi) 
                        vertices = list(p.flattening(distance=0.01))
                        coords = [(v.x, v.y) for v in vertices]
                        
                        if len(coords) >= 2:
                            if entity.is_closed:
                                geom = Polygon(coords)
                            else:
                                geom = LineString(coords)

                    # 4. Circle, Arc, Ellipse, Spline
                    elif dxftype in:
                        # Konversi kurva matematis ke linestring aproksimasi
                        p = path.make_path(entity)
                        vertices = list(p.flattening(distance=0.01))
                        coords = [(v.x, v.y) for v in vertices]
                        
                        if len(coords) >= 2:
                            # Jika Circle atau Spline tertutup, jadikan Polygon
                            if dxftype == 'CIRCLE' or (dxftype == 'SPLINE' and entity.dxf.flags & 1):
                                geom = Polygon(coords)
                            else:
                                geom = LineString(coords)

                    # 5. Hatch (Arsiran) - Dianggap sebagai Polygon
                    elif dxftype == 'HATCH':
                        # Hatch kompleks karena bisa memiliki hole (lubang)
                        # Implementasi sederhana: ambil jalur batas luar
                        p_list = path.make_path(entity)
                        # Biasanya p_list adalah list of paths. Kita ambil yang pertama/terluar.
                        if p_list:
                            vertices = list(p_list.flattening(distance=0.01))
                            coords = [(v.x, v.y) for v in vertices]
                            if len(coords) >= 3:
                                geom = Polygon(coords)

                    # 6. Text/MText - Representasikan sebagai Point dengan atribut teks
                    elif dxftype in:
                        insert = entity.dxf.insert
                        geom = Point(insert.x, insert.y)
                        attribs['text_content'] = entity.dxf.text if dxftype == 'TEXT' else entity.text

                    if geom:
                        # Validasi geometri 
                        if not geom.is_valid:
                            geom = geom.buffer(0) # Trik memperbaiki topologi
                            
                        geometries.append(geom)
                        properties.append(attribs)

                except Exception as ex:
                    logger.debug(f"Gagal mengonversi entitas {dxftype}: {ex}")
                    continue

            if not geometries:
                logger.warning("Tidak ada geometri yang berhasil dikonversi dari file DXF.")
                return gpd.GeoDataFrame()

            # Membuat GeoDataFrame
            gdf = gpd.GeoDataFrame(properties, geometry=geometries)
            if crs:
                gdf.set_crs(crs, inplace=True)
            
            return gdf

        except Exception as e:
            logger.error(f"Gagal memproses DXF dengan ezdxf: {e}")
            raise

    def upload_to_postgis(self, gdf: gpd.GeoDataFrame, table_name: str, schema: str = 'public', if_exists: str = 'append'):
        """
        Mengirim data ke PostGIS. Menangani standarisasi tipe geometri.
        
        Args:
            gdf: GeoDataFrame input.
            table_name: Nama tabel tujuan.
            schema: Schema database (default 'public').
            if_exists: 'fail', 'replace', 'append'.
        """
        if gdf.empty:
            logger.warning("GeoDataFrame kosong. Upload dibatalkan.")
            return

        logger.info(f"Mengunggah {len(gdf)} fitur ke tabel '{schema}.{table_name}'...")

        # Normalisasi Geometri: PostGIS menyukai Multi-Geometry agar konsisten
        # Ubah Polygon -> MultiPolygon, LineString -> MultiLineString, dll.
        # Atau biarkan GeoAlchemy menanganinya dengan tipe GEOMETRY generik.
        
        # Pastikan data memiliki CRS sebelum upload
        if gdf.crs is None:
            logger.error("Data tidak memiliki CRS! PostGIS membutuhkan SRID.")
            # Fallback opsional ke 4326 atau 0, tapi lebih baik raise error
            raise ValueError("GeoDataFrame harus memiliki CRS sebelum upload.")

        try:
            # Menggunakan to_postgis (GeoPandas > 0.8)
            gdf.to_postgis(
                name=table_name,
                con=self.engine,
                schema=schema,
                if_exists=if_exists,
                index=False,
                chunksize=1000, # Optimasi performa upload 
                dtype={'geometry': Geometry(geometry_type='GEOMETRY', srid=gdf.crs.to_epsg())}
            )
            logger.info("Proses upload selesai.")
            
        except Exception as e:
            logger.error(f"Gagal upload ke PostGIS: {e}")
            raise

# --- Contoh Penggunaan (Main Block) ---
if __name__ == "__main__":
    # Konfigurasi Koneksi Database
    # Format: postgresql://username:password@host:port/databasename
    DB_CONN_STR = "postgresql://postgres:password_rahasia@localhost:5432/gis_database"
    
    # Inisialisasi Ingestor
    ingestor = GeoIngestor(DB_CONN_STR)

    # 1. Membaca Shapefile (Contoh: Batas Administrasi)
    try:
        shp_path = "data_input/batas_wilayah.shp"
        # Shapefile biasanya sudah punya.prj, jadi crs_override opsional
        gdf_shp = ingestor.read_file(shp_path)
        ingestor.upload_to_postgis(gdf_shp, "layer_batas_wilayah", if_exists="replace")
    except Exception as e:
        print(f"Skipping SHP: {e}")

    # 2. Membaca DXF (Contoh: Persil Tanah dari CAD)
    try:
        dxf_path = "data_input/persil_tanah.dxf"
        # DXF WAJIB diberi tahu CRS-nya karena tidak menyimpannya. 
        # Misal: UTM Zone 48S (EPSG:32748)
        gdf_dxf = ingestor.read_file(dxf_path, source_crs="EPSG:32748")
        
        # Seringkali kita ingin mengubah ke WGS84 (EPSG:4326) sebelum masuk DB
        if not gdf_dxf.empty:
            gdf_dxf = gdf_dxf.to_crs("EPSG:4326")
            ingestor.upload_to_postgis(gdf_dxf, "layer_persil_cad", if_exists="replace")
    except Exception as e:
        print(f"Skipping DXF: {e}")

    # 3. Membaca GeoJSON (Contoh: Lokasi POI)
    try:
        json_path = "data_input/lokasi_penting.geojson"
        gdf_json = ingestor.read_file(json_path)
        ingestor.upload_to_postgis(gdf_json, "layer_poi", if_exists="replace")
    except Exception as e:
        print(f"Skipping GeoJSON: {e}")
